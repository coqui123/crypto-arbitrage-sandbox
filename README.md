Overview
This script is designed to perform arbitrage trading between two cryptocurrency exchanges: MEXC and Coinbase. It fetches cryptocurrency prices from both exchanges, calculates the Average True Range (ATR) for volatility assessment, and executes trades to exploit price differences. The script also maintains a record of balances and trade history.

Features
Fetch Cryptocurrency Prices: Retrieves the latest prices for specified cryptocurrencies from MEXC and Coinbase.
Price History Management: Initializes and saves price history for each cryptocurrency.
Balance Management: Reads and writes balances to a file, ensuring persistence across script runs.
Trade Execution: Executes buy and sell trades based on price differences between the two exchanges.
ATR Calculation: Calculates the Average True Range (ATR) to determine trade size.
Logging: Logs important events and errors for monitoring and debugging.

Requirements
Python 3.x
requests library
pandas library
logging library
Installation
Clone the repository or download the script.
Install the required libraries using pip:
bash
pip install requests pandas

Configuration
Constants:
TAKER_FEE: The fee for taker trades (default: 0.001 or 0.10%).
MAKER_FEE: The fee for maker trades (default: 0.0 or 0.00%).
MIN_TRADE_AMOUNT: The minimum trade amount in USD (default: 5.0).
TRADE_SIZE_FACTOR: A factor to determine trade size (default: 500000.0).

Usage
Initialize Price History: The script initializes price history for the specified cryptocurrencies on both exchanges.
Read Balances: Reads balances from balances.txt. If the file does not exist, it initializes with default values.
Trade and Hedge: Continuously fetches prices, calculates ATR, and executes trades to exploit price differences.
Write Balances: Writes updated balances to balances.txt.
Log Portfolio Value: Logs the total portfolio value in USD.
Running the Script
To run the script, simply execute the following command:
bash
python script_name.py

Functions
fetch_crypto_price_mexc(symbol): Fetches the price of a cryptocurrency from MEXC.
fetch_crypto_price_coinbase(symbol): Fetches the price of a cryptocurrency from Coinbase.
save_price_history(symbol, price): Saves the price history of a cryptocurrency.
initialize_price_history(symbol, exchange): Initializes the price history for a cryptocurrency on a specified exchange.
read_balances_from_file(): Reads balances from balances.txt.
write_balances_to_file(usd_balance, balances): Writes balances to balances.txt.
record_trade_history(symbol, amount, price, trade_type, exchange): Records trade history.
calculate_atr(symbol, period): Calculates the Average True Range (ATR) for a cryptocurrency.
trade_and_hedge(cryptos, usd_balance, balances): Executes trades to exploit price differences between exchanges.

Logging
The script uses Python's logging module to log important events and errors. Logs are printed to the console with timestamps and log levels.

Notes
Ensure that the balances.txt file is in the same directory as the script.
The script runs indefinitely, fetching prices and executing trades every 15 seconds.

Disclaimer
This script is for educational purposes only. Trading cryptocurrencies involves significant risk, and you should only trade with money you can afford to lose. The author is not responsible for any financial losses incurred.

License
This project is licensed under the MIT License.
