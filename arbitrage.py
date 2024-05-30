import requests
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import time
import logging

# Constants
TAKER_FEE = 0.001  # 0.10%
MAKER_FEE = 0.0  # 0.00%
MIN_TRADE_AMOUNT = 5.0
TRADE_SIZE_FACTOR = 500000.0

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Fetch crypto price from MEXC
def fetch_crypto_price_mexc(symbol):
    try:
        url = f"https://api.mexc.com/api/v3/ticker/price?symbol={symbol}"
        response = requests.get(url)
        response.raise_for_status()
        price = float(response.json()['price'])
        save_price_history(symbol, price)
        return price
    except Exception as e:
        logging.error(f"Error fetching price from MEXC for {symbol}: {e}")
        return None

# Fetch crypto price from Coinbase
def fetch_crypto_price_coinbase(symbol):
    try:
        symbol = symbol.replace("USDT", "-USD")
        url = f"https://api.coinbase.com/v2/prices/{symbol}/spot"
        response = requests.get(url)
        response.raise_for_status()
        price = float(response.json()['data']['amount'])
        save_price_history(symbol.replace('-USD', 'USDT'), price)
        return price
    except Exception as e:
        logging.error(f"Error fetching price from Coinbase for {symbol}: {e}")
        return None

# Save price history
def save_price_history(symbol, price):
    file_path = f"{symbol}_price_history.txt"
    with open(file_path, 'a') as file:
        file.write(f"{datetime.utcnow().isoformat()},{price}\n")

# Initialize price history
def initialize_price_history(symbol, exchange):
    file_path = f"{symbol}_price_history.txt"
    if not os.path.exists(file_path):
        logging.info(f"Initializing price history for {symbol} on {exchange}")
        for _ in range(15):
            if exchange == "mexc":
                fetch_crypto_price_mexc(symbol)
            elif exchange == "coinbase":
                fetch_crypto_price_coinbase(symbol)
            time.sleep(1)

# Read balances from file
def read_balances_from_file():
    balances = {"mexc": {}, "coinbase": {}}
    usd_balance = {"mexc": 2000.0, "coinbase": 2000.0}
    if os.path.exists("balances.txt"):
        with open("balances.txt", 'r') as file:
            for line in file:
                parts = line.strip().split(',')
                if len(parts) != 3:
                    logging.error(f"Skipping malformed line: {line.strip()}")
                    continue
                exchange, currency, amount = parts
                if currency == "USD":
                    usd_balance[exchange] = float(amount)
                else:
                    balances[exchange][currency] = float(amount)
    else:
        with open("balances.txt", 'w') as file:
            for exchange in ["mexc", "coinbase"]:
                file.write(f"{exchange},USD,{usd_balance[exchange]}\n")
                for crypto in ["XTZ", "BTC", "LTC", "BONK", "DOT", "ADA"]:
                    balances[exchange][crypto] = 0.0
                    file.write(f"{exchange},{crypto},{balances[exchange][crypto]}\n")
    return usd_balance, balances

# Write balances to file
def write_balances_to_file(usd_balance, balances):
    with open("balances.txt", 'w') as file:
        for exchange in ["mexc", "coinbase"]:
            file.write(f"{exchange},USD,{usd_balance[exchange]}\n")
            for currency, amount in balances[exchange].items():
                file.write(f"{exchange},{currency},{amount}\n")

# Record trade history
def record_trade_history(symbol, amount, price, trade_type, exchange):
    file_path = f"{symbol}_trade_history.txt"
    with open(file_path, 'a') as file:
        file.write(f"{datetime.utcnow().isoformat()},{trade_type},{amount},{price},{amount * price},{exchange}\n")

# Calculate ATR
def calculate_atr(symbol, period):
    file_path = f"{symbol}_price_history.txt"
    if not os.path.exists(file_path):
        raise FileNotFoundError("Price history file not found")

    prices = pd.read_csv(file_path, header=None, names=['timestamp', 'price'])
    if len(prices) < period + 1:
        raise ValueError("Not enough data to calculate ATR")

    prices['price'] = prices['price'].astype(float)
    prices['prev_close'] = prices['price'].shift(1)
    prices['tr'] = prices.apply(lambda row: max(row['price'] - row['price'], abs(row['price'] - row['prev_close']),
                                                abs(row['price'] - row['prev_close'])), axis=1)
    atr = prices['tr'].rolling(window=period).mean().iloc[-1]

    return atr

# Trade and hedge
def trade_and_hedge(cryptos, usd_balance, balances):
    prices_mexc = {crypto: fetch_crypto_price_mexc(crypto) for crypto in cryptos}
    prices_coinbase = {crypto: fetch_crypto_price_coinbase(crypto) for crypto in cryptos}

    for crypto in cryptos:
        crypto_name = crypto.replace("USDT", "")
        last_price = balances["mexc"].get(crypto_name, prices_mexc[crypto])
        try:
            atr = calculate_atr(crypto, 14)
        except (ValueError, FileNotFoundError) as e:
            logging.error(f"Error calculating ATR for {crypto}: {e}")
            atr = 0

        trade_size_factor = max(MIN_TRADE_AMOUNT / TRADE_SIZE_FACTOR, atr / prices_mexc[crypto])
        trade_amount_usd = TRADE_SIZE_FACTOR * trade_size_factor

        if trade_amount_usd < MIN_TRADE_AMOUNT:
            continue

        if prices_mexc[crypto] and prices_coinbase[crypto]:
            if prices_mexc[crypto] < prices_coinbase[crypto]:
                if usd_balance["mexc"] >= trade_amount_usd:
                    crypto_amount = trade_amount_usd / prices_mexc[crypto]
                    fee = trade_amount_usd * TAKER_FEE
                    net_trade_amount_usd = trade_amount_usd - fee
                    balances["mexc"][crypto_name] = balances["mexc"].get(crypto_name, 0.0) + crypto_amount
                    usd_balance["mexc"] -= net_trade_amount_usd
                    logging.info(f"Arbitrage: Bought {crypto_amount:.10f} of {crypto} on MEXC for ${net_trade_amount_usd:.2f} (Fee: ${fee:.2f})")
                    record_trade_history(crypto, crypto_amount, prices_mexc[crypto], "buy", "mexc")
                    usd_balance["coinbase"] += crypto_amount * prices_coinbase[crypto]
                    logging.info(f"Arbitrage: Sold {crypto_amount:.10f} of {crypto} on Coinbase for ${crypto_amount * prices_coinbase[crypto]:.2f}")
                    record_trade_history(crypto, -crypto_amount, prices_coinbase[crypto], "sell", "coinbase")
            else:
                if usd_balance["coinbase"] >= trade_amount_usd:
                    crypto_amount = trade_amount_usd / prices_coinbase[crypto]
                    fee = trade_amount_usd * TAKER_FEE
                    net_trade_amount_usd = trade_amount_usd - fee
                    balances["coinbase"][crypto_name] = balances["coinbase"].get(crypto_name, 0.0) + crypto_amount
                    usd_balance["coinbase"] -= net_trade_amount_usd
                    logging.info(f"Arbitrage: Bought {crypto_amount:.10f} of {crypto} on Coinbase for ${net_trade_amount_usd:.2f} (Fee: ${fee:.2f})")
                    record_trade_history(crypto, crypto_amount, prices_coinbase[crypto], "buy", "coinbase")
                    usd_balance["mexc"] += crypto_amount * prices_mexc[crypto]
                    logging.info(f"Arbitrage: Sold {crypto_amount:.10f} of {crypto} on MEXC for ${crypto_amount * prices_mexc[crypto]:.2f}")
                    record_trade_history(crypto, -crypto_amount, prices_mexc[crypto], "sell", "mexc")

    return usd_balance, balances

# Main function
def main():
    usd_balance, balances = read_balances_from_file()
    cryptos = ["XTZUSDT","BONKUSDT","DOTUSDT"]

    for crypto in cryptos:
        try:
            initialize_price_history(crypto, "mexc")
            initialize_price_history(crypto, "coinbase")
        except Exception as e:
            logging.error(f"Error initializing price history for {crypto}: {e}")

    while True:
        usd_balance, balances = trade_and_hedge(cryptos, usd_balance, balances)
        write_balances_to_file(usd_balance, balances)

        current_portfolio_value = sum(usd_balance.values())
        for exchange in ["mexc", "coinbase"]:
            for crypto, amount in balances[exchange].items():
                try:
                    price_mexc = fetch_crypto_price_mexc(f"{crypto}USDT")
                    price_coinbase = fetch_crypto_price_coinbase(f"{crypto}-USD")
                    current_portfolio_value += amount * max(price_mexc, price_coinbase)
                except Exception as e:
                    logging.error(f"Error fetching price for {crypto}: {e}")

        logging.info(f"Total Portfolio Value in USD: {current_portfolio_value:.2f}")
        time.sleep(15)

if __name__ == "__main__":
    main()
