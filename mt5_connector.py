
### mt5_connector.py

"""
MetaTrader 5 Connector Service
Provides real-time OHLC data to the trading system
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import redis
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import threading
import zmq

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MT5Connector:
    """Manages connection to MetaTrader 5 and data streaming"""
    
    def __init__(self, redis_host: str = "redis", redis_port: int = 6379):
        """Initialize MT5 connector"""
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        
        # ZMQ for real-time data streaming
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind("tcp://*:5555")
        
        # MT5 connection status
        self.connected = False
        self.symbol = "EURUSD"
        self.timeframe = mt5.TIMEFRAME_M15
        
        # Data update settings
        self.update_interval = 1  # seconds
        self.lookback_bars = 1000
        
        # Thread control
        self.running = False
        self.data_thread = None
        
    def connect(self, login: int, password: str, server: str) -> bool:
        """Connect to MetaTrader 5"""
        try:
            # Initialize MT5
            if not mt5.initialize():
                logger.error("MT5 initialization failed")
                return False
            
            # Login to account
            authorized = mt5.login(login, password=password, server=server)
            if not authorized:
                logger.error(f"Failed to login to MT5: {mt5.last_error()}")
                mt5.shutdown()
                return False
            
            self.connected = True
            logger.info(f"Connected to MT5 - Account: {login}, Server: {server}")
            
            # Get account info
            account_info = mt5.account_info()
            if account_info:
                logger.info(f"Account Balance: {account_info.balance}, "
                          f"Currency: {account_info.currency}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to MT5: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MetaTrader 5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5")
    
    def get_ohlc_data(self, symbol: str = None, timeframe: int = None, 
                     count: int = None) -> Optional[pd.DataFrame]:
        """Get OHLC data from MT5"""
        if not self.connected:
            logger.error("Not connected to MT5")
            return None
        
        symbol = symbol or self.symbol
        timeframe = timeframe or self.timeframe
        count = count or self.lookback_bars
        
        try:
            # Get rates
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            
            if rates is None or len(rates) == 0:
                logger.error(f"Failed to get rates for {symbol}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            
            # Convert time to datetime
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            
            # Rename columns to match system
            df.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'tick_volume': 'volume'
            }, inplace=True)
            
            # Select only OHLCV columns
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting OHLC data: {e}")
            return None
    
    def get_tick_data(self, symbol: str = None) -> Optional[Dict]:
        """Get current tick data"""
        if not self.connected:
            return None
        
        symbol = symbol or self.symbol
        
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None
            
            return {
                'time': datetime.fromtimestamp(tick.time),
                'bid': tick.bid,
                'ask': tick.ask,
                'last': tick.last,
                'volume': tick.volume
            }
            
        except Exception as e:
            logger.error(f"Error getting tick data: {e}")
            return None
    
    def start_data_stream(self):
        """Start streaming data to Redis and ZMQ"""
        if self.running:
            logger.warning("Data stream already running")
            return
        
        self.running = True
        self.data_thread = threading.Thread(target=self._data_stream_loop)
        self.data_thread.start()
        logger.info("Started data streaming")
    
    def stop_data_stream(self):
        """Stop data streaming"""
        self.running = False
        if self.data_thread:
            self.data_thread.join()
        logger.info("Stopped data streaming")
    
    def _data_stream_loop(self):
        """Main data streaming loop"""
        while self.running:
            try:
                # Get OHLC data
                df = self.get_ohlc_data()
                if df is not None:
                    # Store in Redis
                    self._store_ohlc_redis(df)
                    
                    # Publish via ZMQ
                    self._publish_ohlc_zmq(df)
                
                # Get tick data
                tick = self.get_tick_data()
                if tick:
                    # Store current price in Redis
                    self.redis_client.hset(
                        "mt5:current_price",
                        mapping={
                            'symbol': self.symbol,
                            'bid': tick['bid'],
                            'ask': tick['ask'],
                            'time': tick['time'].isoformat()
                        }
                    )
                    
                    # Publish tick via ZMQ
                    tick_msg = {
                        'type': 'tick',
                        'data': {
                            'symbol': self.symbol,
                            'bid': tick['bid'],
                            'ask': tick['ask'],
                            'time': tick['time'].isoformat()
                        }
                    }
                    self.publisher.send_json(tick_msg)
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in data stream loop: {e}")
                time.sleep(5)  # Wait before retry
    
    def _store_ohlc_redis(self, df: pd.DataFrame):
        """Store OHLC data in Redis"""
        try:
            # Convert DataFrame to JSON
            df_reset = df.reset_index()
            df_reset['time'] = df_reset['time'].astype(str)
            
            # Store full dataset
            self.redis_client.set(
                f"mt5:ohlc:{self.symbol}:{self.timeframe}",
                json.dumps(df_reset.to_dict()),
                ex=300  # Expire after 5 minutes
            )
            
            # Store latest candle
            latest = df.iloc[-1]
            self.redis_client.hset(
                f"mt5:latest_candle:{self.symbol}",
                mapping={
                    'open': latest['open'],
                    'high': latest['high'],
                    'low': latest['low'],
                    'close': latest['close'],
                    'volume': latest['volume'],
                    'time': df.index[-1].isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error storing data in Redis: {e}")
    
    def _publish_ohlc_zmq(self, df: pd.DataFrame):
        """Publish OHLC data via ZMQ"""
        try:
            # Send latest candles
            recent_data = df.tail(10).reset_index()
            recent_data['time'] = recent_data['time'].astype(str)
            
            msg = {
                'type': 'ohlc',
                'symbol': self.symbol,
                'timeframe': self.timeframe,
                'data': recent_data.to_dict('records')
            }
            
            self.publisher.send_json(msg)
            
        except Exception as e:
            logger.error(f"Error publishing via ZMQ: {e}")
    
    def get_account_info(self) -> Optional[Dict]:
        """Get account information"""
        if not self.connected:
            return None
        
        try:
            info = mt5.account_info()
            if info is None:
                return None
            
            return {
                'login': info.login,
                'balance': info.balance,
                'equity': info.equity,
                'margin': info.margin,
                'free_margin': info.margin_free,
                'currency': info.currency,
                'leverage': info.leverage,
                'profit': info.profit
            }
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    def place_order(self, order_type: str, symbol: str, volume: float,
                   price: float = None, sl: float = None, tp: float = None,
                   comment: str = "") -> Optional[int]:
        """Place an order in MT5"""
        if not self.connected:
            logger.error("Not connected to MT5")
            return None
        
        try:
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error(f"Symbol {symbol} not found")
                return None
            
            # Prepare request
            if order_type.upper() == "BUY":
                trade_type = mt5.ORDER_TYPE_BUY
                price = price or symbol_info.ask
            elif order_type.upper() == "SELL":
                trade_type = mt5.ORDER_TYPE_SELL
                price = price or symbol_info.bid
            else:
                logger.error(f"Invalid order type: {order_type}")
                return None
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": trade_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 234000,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send order
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Order failed: {result.comment}")
                return None
            
            logger.info(f"Order placed successfully. Ticket: {result.order}")
            return result.order
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    def close_position(self, ticket: int) -> bool:
        """Close a position by ticket"""
        if not self.connected:
            return False
        
        try:
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.error(f"Position {ticket} not found")
                return False
            
            position = position[0]
            
            # Prepare close request
            symbol_info = mt5.symbol_info(position.symbol)
            
            if position.type == mt5.POSITION_TYPE_BUY:
                trade_type = mt5.ORDER_TYPE_SELL
                price = symbol_info.bid
            else:
                trade_type = mt5.ORDER_TYPE_BUY
                price = symbol_info.ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": ticket,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": trade_type,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "Close position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Failed to close position: {result.comment}")
                return False
            
            logger.info(f"Position {ticket} closed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return False


def main():
    """Main function to run MT5 connector"""
    # Get configuration from environment
    import os
    
    mt5_login = int(os.getenv('MT5_LOGIN', '0'))
    mt5_password = os.getenv('MT5_PASSWORD', '')
    mt5_server = os.getenv('MT5_SERVER', '')
    redis_host = os.getenv('REDIS_HOST', 'redis')
    
    if not all([mt5_login, mt5_password, mt5_server]):
        logger.error("MT5 credentials not provided in environment variables")
        return
    
    # Create connector
    connector = MT5Connector(redis_host=redis_host)
    
    # Connect to MT5
    if not connector.connect(mt5_login, mt5_password, mt5_server):
        logger.error("Failed to connect to MT5")
        return
    
    try:
        # Start data streaming
        connector.start_data_stream()
        
        # Keep running
        while True:
            # Log status every minute
            time.sleep(60)
            account_info = connector.get_account_info()
            if account_info:
                logger.info(f"Account Status - Balance: {account_info['balance']}, "
                          f"Equity: {account_info['equity']}")
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        connector.stop_data_stream()
        connector.disconnect()


if __name__ == "__main__":
    main()