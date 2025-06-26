#!/usr/bin/env python3
"""
MT5 Connector Wine Adapter
Bridges the Wine-based MT5 (via RPyC) to your existing Redis/ZMQ architecture
"""

import time
import logging
import json
import redis
import pandas as pd
import numpy as np
from datetime import datetime
import threading
import signal
import sys
import os
import zmq
from mt5linux import MetaTrader5

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MT5WineConnector:
    """Enhanced MT5 Connector that works with Wine-based MT5 via RPyC"""
    
    def __init__(self):
        # Redis connection
        self.redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
        
        # ZMQ Publisher (maintaining your existing architecture)
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind("tcp://*:5555")
        
        # MT5 connection via RPyC
        self.mt5 = None
        self.connected = False
        self.running = False
        
        # Get credentials from environment
        self.login = int(os.getenv('MT5_LOGIN', '7920878'))
        self.password = os.getenv('MT5_PASSWORD', 'Srm@2025')
        self.server = os.getenv('MT5_SERVER', 'Eightcap-Demo')
        
        # Symbol and timeframe settings
        self.symbol = "EURUSD"
        self.timeframe = 15  # M15
        
    def connect(self, max_retries=30, retry_delay=5):
        """Connect to MT5 via RPyC with retries"""
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempting to connect to MT5 via RPyC (attempt {attempt + 1}/{max_retries})")
                
                # Connect to MT5 via RPyC on localhost
                # The Wine container exposes MT5 on port 8001
                self.mt5 = MetaTrader5(host="mt5-wine-standard", port=8001)
                
                # Initialize connection
                if not self.mt5.initialize():
                    error = self.mt5.last_error()
                    logger.error(f"MT5 initialization failed: {error}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        return False
                
                # Login to account
                if not self.mt5.login(self.login, self.password, self.server):
                    error = self.mt5.last_error()
                    logger.error(f"MT5 login failed: {error}")
                    
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return False
                
                # Successfully connected
                self.connected = True
                logger.info("Successfully connected to MT5 via Wine/RPyC!")
                
                # Get and log account info
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
                        'last_update': datetime.now().isoformat(),
                        'connection_type': 'wine_rpyc'
                    })
                
                # Check available symbols
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
        """Main data streaming loop - maintains compatibility with your existing system"""
        while self.running and self.connected:
            try:
                # Get symbols
                major_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD']
                
                for symbol_name in major_pairs:
                    # Check if symbol exists and is visible
                    symbol_info = self.mt5.symbol_info(symbol_name)
                    if symbol_info is None:
                        continue
                        
                    if not symbol_info.visible:
                        if not self.mt5.symbol_select(symbol_name, True):
                            logger.warning(f"Failed to select symbol {symbol_name}")
                            continue
                    
                    # Get OHLC data - using numeric timeframe constant
                    rates = self.mt5.copy_rates_from_pos(
                        symbol_name, 
                        self.mt5.TIMEFRAME_M15,  # 15 minute timeframe
                        0, 
                        1000
                    )
                    
                    if rates is not None and len(rates) > 0:
                        # Convert to DataFrame
                        df = pd.DataFrame(rates)
                        df['time'] = pd.to_datetime(df['time'], unit='s')
                        
                        # Store in Redis (maintaining your existing structure)
                        df_dict = df.to_dict()
                        df_dict['time'] = [t.isoformat() for t in df['time']]
                        
                        self.redis_client.set(
                            f'mt5:ohlc:{symbol_name}:15',
                            json.dumps(df_dict),
                            ex=300
                        )
                        
                        # Publish via ZMQ (maintaining your existing architecture)
                        zmq_msg = {
                            'type': 'ohlc',
                            'symbol': symbol_name,
                            'timeframe': 15,
                            'data': df_dict
                        }
                        self.publisher.send_json(zmq_msg)
                        
                        # Store latest tick
                        tick = self.mt5.symbol_info_tick(symbol_name)
                        if tick:
                            tick_data = {
                                'bid': tick.bid,
                                'ask': tick.ask,
                                'last': tick.last,
                                'volume': tick.volume,
                                'time': datetime.fromtimestamp(tick.time).isoformat()
                            }
                            
                            self.redis_client.hset(f'mt5:tick:{symbol_name}', mapping=tick_data)
                            
                            # Publish tick via ZMQ
                            zmq_tick_msg = {
                                'type': 'tick',
                                'symbol': symbol_name,
                                'data': tick_data
                            }
                            self.publisher.send_json(zmq_tick_msg)
                
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
        """Place a trading order - maintains compatibility with your existing system"""
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
            
            # Get current prices
            tick = self.mt5.symbol_info_tick(symbol)
            if not tick:
                logger.error(f"Failed to get tick for {symbol}")
                return None
            
            # Prepare order request
            point = symbol_info.point
            
            if order_type.upper() == "BUY":
                trade_type = self.mt5.ORDER_TYPE_BUY
                price = tick.ask
            else:
                trade_type = self.mt5.ORDER_TYPE_SELL
                price = tick.bid
            
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
        # Wait for Wine/MT5 to fully start
        logger.info("Waiting for Wine/MT5 to initialize...")
        time.sleep(30)  # Give Wine time to start
        
        # Connect to MT5
        if not self.connect():
            logger.error("Failed to connect to MT5")
            return
        
        # Start data streaming
        self.start_data_streaming()
        
        # Monitor Redis for trading commands
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe('mt5:commands')
        
        logger.info("MT5 Wine Connector is running. Listening for commands...")
        
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
        if self.context:
            self.context.term()
        logger.info("MT5 Wine Connector shut down")


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Shutdown signal received")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    connector = MT5WineConnector()
    connector.run()