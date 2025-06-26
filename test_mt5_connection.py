from mt5linux import MetaTrader5
import time

print("Connecting to MT5...")
mt5 = MetaTrader5(host='localhost', port=18812)

if mt5.initialize():
    print("Connected successfully!")
    
    # Get account info
    account = mt5.account_info()
    if account:
        print(f"Account: {account.login}")
        print(f"Balance: {account.balance}")
        print(f"Server: {account.server}")
    
    # Get symbol info
    symbol = mt5.symbol_info("EURUSD")
    if symbol:
        print(f"\nEURUSD Bid: {symbol.bid}")
        print(f"EURUSD Ask: {symbol.ask}")
    
    mt5.shutdown()
else:
    print("Failed to connect to MT5")
    print(mt5.last_error())
