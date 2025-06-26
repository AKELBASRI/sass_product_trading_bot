# mt5_connector_enhanced.py - Updated with auto-login
#!/usr/bin/env python3
"""
Enhanced MT5 Connector with Auto-Trading Support
"""

import time
import logging
import json
import redis
import pandas as pd
import numpy as np
from datetime import datetime
from mt5linux import MetaTrader5
import threading
import signal
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedMT5Connector:
    def __init__(self):
        self.mt5 = None
        self.redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
        self.running = False
        self.connected = False
        
        # Get credentials from environment or use defaults
        self.login = int(os.getenv('MT5_LOGIN', '7920878'))
        self.password = os.getenv('MT5_PASSWORD', 'Srm@2025')
        self.server = os.getenv('MT5_SERVER', 'Eightcap-Demo')
        
    def connect(self, max_retries=10, retry_delay=5):
        """Connect to MT5 with retries"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to connect to MT5 (attempt {attempt + 1}/{max_retries})")
                
                # Initialize mt5linux connection
                self.mt5 = MetaTrader5(host='localhost', port=18812)
                
                if not self.mt5.initialize(
                    login=self.login,
                    password=self.password,
                    server=self.server
                ):
                    error = self.mt5.last_error()
                    logger.error(f"MT5 initialization failed: {error}")
                    
                    # If it's a connection error, wait and retry
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        return False
                
                # Successfully connected
                self.connected = True
                logger.info("Successfully connected to MT5!")
                
                # Get account info
                account_info = self.mt5.account_info()
                if account_info:
                    logger.info(f"Account: {account_info.login}")
                    logger.info(f"Server: {account_info.server}")
                    logger.info(f"Balance: {account_info.balance}")
                    logger.info(f"Currency: {account_info.currency}")
                    logger.info(f"Leverage: {account_info.leverage}")
                    
                    # Store connection status in Redis
                    self.redis_client.hset('mt5:status', mapping={
                        'connected': 'true',
                        'account': str(account_info.login),
                        'server': account_info.server,
                        'balance': str(account_info.balance),
                        'currency': account_info.currency,
                        'last_update': datetime.now().isoformat()
                    })
                
                # Check if symbol data is available
                symbols = self.mt5.symbols_get()
                if symbols:
                    logger.info(f"Available symbols: {len(symbols)}")
                    # List first 10 symbols
                    for i, symbol in enumerate(symbols[:10]):
                        logger.info(f"  {symbol.name}")
                
                return True
                    
            except Exception as e:
                logger.error(f"Connection error: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
        
        return False
    
    def start_data_streaming(self):
        """Start streaming market data"""
        self.running = True
        thread = threading.Thread(target=self._data_stream_loop)
        thread.daemon = True
        thread.start()
        logger.info("Started data streaming thread")
        
    def _data_stream_loop(self):
        """Main data streaming loop"""
        while self.running and self.connected:
            try:
                # Get symbols
                symbols = self.mt5.symbols_get()
                if symbols:
                    # Focus on major pairs
                    major_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD']
                    
                    for symbol_name in major_pairs:
                        # Check if symbol exists
                        symbol_info = self.mt5.symbol_info(symbol_name)
                        if symbol_info is None:
                            continue
                            
                        if not symbol_info.visible:
                            # Try to enable symbol
                            if not self.mt5.symbol_select(symbol_name, True):
                                logger.warning(f"Failed to select symbol {symbol_name}")
                                continue
                        
                        # Get OHLC data
                        rates = self.mt5.copy_rates_from_pos(
                            symbol_name, 
                            self.mt5.TIMEFRAME_M15, 
                            0, 
                            1000
                        )
                        
                        if rates is not None and len(rates) > 0:
                            # Convert to DataFrame
                            df = pd.DataFrame(rates)
                            df['time'] = pd.to_datetime(df['time'], unit='s')
                            
                            # Store in Redis
                            df_dict = df.to_dict()
                            df_dict['time'] = [t.isoformat() for t in df['time']]
                            
                            self.redis_client.set(
                                f'mt5:ohlc:{symbol_name}:15',
                                json.dumps(df_dict),
                                ex=300
                            )
                            
                            # Store latest tick
                            tick = self.mt5.symbol_info_tick(symbol_name)
                            if tick:
                                self.redis_client.hset(f'mt5:tick:{symbol_name}', mapping={
                                    'bid': tick.bid,
                                    'ask': tick.ask,
                                    'last': tick.last,
                                    'volume': tick.volume,
                                    'time': datetime.fromtimestamp(tick.time).isoformat()
                                })
                
                # Update account info
                account_info = self.mt5.account_info()
                if account_info:
                    self.redis_client.hset('mt5:account', mapping={
                        'balance': account_info.balance,
                        'equity': account_info.equity,
                        'margin': account_info.margin,
                        'free_margin': account_info.margin_free,
                        'profit': account_info.profit,
                        'last_update': datetime.now().isoformat()
                    })
                
                # Get open positions
                positions = self.mt5.positions_get()
                if positions is not None:
                    positions_data = []
                    for pos in positions:
                        positions_data.append({
                            'ticket': pos.ticket,
                            'symbol': pos.symbol,
                            'type': 'buy' if pos.type == 0 else 'sell',
                            'volume': pos.volume,
                            'price_open': pos.price_open,
                            'sl': pos.sl,
                            'tp': pos.tp,
                            'profit': pos.profit,
                            'time': datetime.fromtimestamp(pos.time).isoformat()
                        })
                    
                    self.redis_client.set(
                        'mt5:positions',
                        json.dumps(positions_data),
                        ex=60
                    )
                
                time.sleep(1)  # Update every second
                
            except Exception as e:
                logger.error(f"Error in data stream: {e}")
                time.sleep(5)
    
    def place_order(self, symbol, order_type, volume, sl=None, tp=None, comment=""):
        """Place a trading order"""
        if not self.connected:
            logger.error("Not connected to MT5")
            return None
            
        try:
            # Get symbol info
            symbol_info = self.mt5.symbol_info(symbol)
            if not symbol_info:
                logger.error(f"Symbol {symbol} not found")
                return None
                
            if not symbol_info.visible:
                if not self.mt5.symbol_select(symbol, True):
                    logger.error(f"Failed to select symbol {symbol}")
                    return None
            
            # Prepare order request
            point = symbol_info.point
            
            if order_type.upper() == "BUY":
                trade_type = self.mt5.ORDER_TYPE_BUY
                price = self.mt5.symbol_info_tick(symbol).ask
            else:
                trade_type = self.mt5.ORDER_TYPE_SELL
                price = self.mt5.symbol_info_tick(symbol).bid
            
            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": trade_type,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": comment,
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }
            
            if sl:
                request["sl"] = sl
            if tp:
                request["tp"] = tp
            
            # Send order
            result = self.mt5.order_send(request)
            
            if result.retcode != self.mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order failed: {result.comment}")
                return None
            
            logger.info(f"Order placed successfully: {result}")
            return result.order
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    def run(self):
        """Main run loop"""
        # Connect to MT5
        if not self.connect():
            logger.error("Failed to connect to MT5")
            return
        
        # Start data streaming
        self.start_data_streaming()
        
        # Monitor Redis for trading commands
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe('mt5:commands')
        
        logger.info("MT5 Connector is running. Listening for commands...")
        
        try:
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        command = json.loads(message['data'])
                        
                        if command['action'] == 'place_order':
                            result = self.place_order(
                                command['symbol'],
                                command['order_type'],
                                command['volume'],
                                command.get('sl'),
                                command.get('tp'),
                                command.get('comment', '')
                            )
                            
                            # Publish result
                            self.redis_client.publish('mt5:results', json.dumps({
                                'command_id': command.get('id'),
                                'success': result is not None,
                                'order_id': result
                            }))
                            
                    except Exception as e:
                        logger.error(f"Error processing command: {e}")
                        
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        self.running = False
        if self.mt5:
            self.mt5.shutdown()
        logger.info("MT5 Connector shut down")


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Shutdown signal received")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    connector = EnhancedMT5Connector()
    connector.run()
