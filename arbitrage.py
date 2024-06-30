import requests
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import time
import logging

# Constants
TAKER_FEE = 0.001  # 0.10% fee for taker orders (immediate execution)
MAKER_FEE = 0.0    # 0.00% fee for maker orders (limit orders)
MIN_TRADE_AMOUNT = 5.0  # Minimum trade amount in USD
TRADE_SIZE_FACTOR = 500000.0  # Factor used to calculate trade size

# Configure logging to track script execution and errors
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_crypto_price_mexc(symbol):
    """
    Fetch the current price of a cryptocurrency from the MEXC exchange.
    
    Args:
    symbol (str): The trading pair symbol (e.g., 'BTCUSDT')
    
    Returns:
    float: The current price of the cryptocurrency
    """
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

def fetch_crypto_price_coinbase(symbol):
    """
    Fetch the current price of a cryptocurrency from the Coinbase exchange.
    
    Args:
    symbol (str): The trading pair symbol (e.g., 'BTC-USD')
    
    Returns:
    float: The current price of the cryptocurrency
    """
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

def save_price_history(symbol, price):
    """
    Save the current price of a cryptocurrency to a historical price file.
    
    Args:
    symbol (str): The trading pair symbol
    price (float): The current price of the cryptocurrency
    """
    file_path = f"{symbol}_price_history.txt"
    with open(file_path, 'a') as file:
        file.write(f"{datetime.utcnow().isoformat()},{price}\n")

def initialize_price_history(symbol, exchange):
    """
    Initialize the price history file for a cryptocurrency if it doesn't exist.
    
    Args:
    symbol (str): The trading pair symbol
    exchange (str): The exchange name ('mexc' or 'coinbase')
    """
    file_path = f"{symbol}_price_history.txt"
    if not os.path.exists(file_path):
        logging.info(f"Initializing price history for {symbol} on {exchange}")
        for _ in range(15):
            if exchange == "mexc":
                fetch_crypto_price_mexc(symbol)
            elif exchange == "coinbase":
                fetch_crypto_price_coinbase(symbol)
            time.sleep(1)

def read_balances_from_file():
    """
    Read cryptocurrency balances from a file or create initial balances if the file doesn't exist.
    
    Returns:
    tuple: A tuple containing two dictionaries (usd_balance, balances)
    """
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

def write_balances_to_file(usd_balance, balances):
    """
    Write current balances to the balances file.
    
    Args:
    usd_balance (dict): Dictionary containing USD balances for each exchange
    balances (dict): Dictionary containing cryptocurrency balances for each exchange
    """
    with open("balances.txt", 'w') as file:
        for exchange in ["mexc", "coinbase"]:
            file.write(f"{exchange},USD,{usd_balance[exchange]}\n")
            for currency, amount in balances[exchange].items():
                file.write(f"{exchange},{currency},{amount}\n")

def record_trade_history(symbol, amount, price, trade_type, exchange):
    """
    Record a trade in the trade history file.
    
    Args:
    symbol (str): The trading pair symbol
    amount (float): The amount of cryptocurrency traded
    price (float): The price at which the trade occurred
    trade_type (str): The type of trade ('buy' or 'sell')
    exchange (str): The exchange where the trade occurred
    """
    file_path = f"{symbol}_trade_history.txt"
    with open(file_path, 'a') as file:
        file.write(f"{datetime.utcnow().isoformat()},{trade_type},{amount},{price},{amount * price},{exchange}\n")

def calculate_atr(symbol, period):
    """
    Calculate the Average True Range (ATR) for a cryptocurrency.
    
    Args:
    symbol (str): The trading pair symbol
    period (int): The number of periods to use for ATR calculation
    
    Returns:
    float: The calculated ATR value
    """
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

def trade_and_hedge(cryptos, usd_balance, balances):
    """
    Execute trades and hedging strategies based on price differences between exchanges.
    
    Args:
    cryptos (list): List of cryptocurrency symbols to trade
    usd_balance (dict): Dictionary containing USD balances for each exchange
    balances (dict): Dictionary containing cryptocurrency balances for each exchange
    
    Returns:
    tuple: Updated usd_balance and balances dictionaries
    """
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
                # Buy on MEXC, sell on Coinbase
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
                # Buy on Coinbase, sell on MEXC
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

def main():
    """
    Main function to run the cryptocurrency trading bot.
    """
    usd_balance, balances = read_balances_from_file()
    cryptos = ["XTZUSDT", "BONKUSDT", "DOTUSDT"]
    
    # Initialize price history for each cryptocurrency
    for crypto in cryptos:
        try:
            initialize_price_history(crypto, "mexc")
            initialize_price_history(crypto, "coinbase")
        except Exception as e:
            logging.error(f"Error initializing price history for {crypto}: {e}")
    
    # Main trading loop
    while True:
        usd_balance, balances = trade_and_hedge(cryptos, usd_balance, balances)
        write_balances_to_file(usd_balance, balances)
        
        # Calculate and log the current portfolio value
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
        
        # Wait for 15 seconds before the next iteration
        time.sleep(15)

if __name__ == "__main__":
    main()
