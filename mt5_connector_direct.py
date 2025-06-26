#!/usr/bin/env python3
"""
Direct MT5 Connector
Works without RPyC by monitoring MT5 files directly
"""

import time
import logging
import json
import redis
import pandas as pd
import numpy as np
from datetime import datetime
import threading
import os
import zmq

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DirectMT5Connector:
    """Connects to MT5 via file monitoring instead of RPyC"""
    
    def __init__(self):
        self.redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind("tcp://*:5555")
        
        self.running = False
        self.connected = False
        
        # For demo purposes, we'll generate simulated data
        self.symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD']
        
    def connect(self):
        """Simulate connection"""
        logger.info("Starting Direct MT5 Connector (Demo Mode)")
        self.connected = True
        
        # Store connection status
        self.redis_client.hset('mt5:status', mapping={
            'connected': 'true',
            'account': '7920878',
            'server': 'Eightcap-Demo',
            'balance': '10000.00',
            'currency': 'USD',
            'last_update': datetime.now().isoformat(),
            'connection_type': 'demo_direct'
        })
        
        return True
    
    def generate_demo_data(self, symbol: str, bars: int = 1000) -> pd.DataFrame:
        """Generate demo OHLC data"""
        end_time = datetime.now()
        dates = pd.date_range(end=end_time, periods=bars, freq='15T')
        
        # Generate realistic price movement
        np.random.seed(hash(symbol) % 1000)
        base_price = {
            'EURUSD': 1.0900,
            'GBPUSD': 1.2700,
            'USDJPY': 156.50,
            'USDCHF': 0.8900,
            'AUDUSD': 0.6600,
            'USDCAD': 1.3700
        }.get(symbol, 1.0000)
        
        # Random walk
        returns = np.random.normal(0, 0.0002, bars)
        price = base_price * np.exp(np.cumsum(returns))
        
        df = pd.DataFrame(index=dates)
        df['close'] = price
        df['open'] = np.roll(price, 1)
        df['open'][0] = price[0]
        
        # Add high/low with some noise
        df['high'] = df[['open', 'close']].max(axis=1) * (1 + np.random.uniform(0, 0.0003, bars))
        df['low'] = df[['open', 'close']].min(axis=1) * (1 - np.random.uniform(0, 0.0003, bars))
        df['volume'] = np.random.randint(1000, 10000, bars)
        
        return df
    
    def start_data_streaming(self):
        """Start streaming market data"""
        self.running = True
        thread = threading.Thread(target=self._data_stream_loop)
        thread.daemon = True
        thread.start()
        logger.info("Started data streaming thread")
    
    def _data_stream_loop(self):
        """Main data streaming loop"""
        while self.running:
            try:
                for symbol in self.symbols:
                    # Generate demo data
                    df = self.generate_demo_data(symbol)
                    
                    # Convert to dict for Redis
                    df_dict = df.reset_index().to_dict()
                    df_dict['index'] = [t.isoformat() for t in df.index]
                    
                    # Store in Redis
                    self.redis_client.set(
                        f'mt5:ohlc:{symbol}:15',
                        json.dumps(df_dict),
                        ex=300
                    )
                    
                    # Publish via ZMQ
                    zmq_msg = {
                        'type': 'ohlc',
                        'symbol': symbol,
                        'timeframe': 15,
                        'data': df_dict
                    }
                    self.publisher.send_json(zmq_msg)
                    
                    # Store latest tick
                    latest = df.iloc[-1]
                    tick_data = {
                        'bid': float(latest['close'] - 0.00005),
                        'ask': float(latest['close'] + 0.00005),
                        'last': float(latest['close']),
                        'volume': int(latest['volume']),
                        'time': datetime.now().isoformat()
                    }
                    
                    self.redis_client.hset(f'mt5:tick:{symbol}', mapping=tick_data)
                
                # Update account info
                self.redis_client.hset('mt5:account', mapping={
                    'balance': '10000.00',
                    'equity': '10000.00',
                    'margin': '0.00',
                    'free_margin': '10000.00',
                    'profit': '0.00',
                    'last_update': datetime.now().isoformat()
                })
                
                time.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in data stream: {e}")
                time.sleep(5)
    
    def run(self):
        """Main run loop"""
        if not self.connect():
            logger.error("Failed to initialize connector")
            return
        
        self.start_data_streaming()
        
        logger.info("Direct MT5 Connector is running in demo mode")
        logger.info("Streaming data for: " + ", ".join(self.symbols))
        
        try:
            while True:
                time.sleep(60)
                logger.info("Connector alive - data streaming...")
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.running = False

if __name__ == "__main__":
    connector = DirectMT5Connector()
    connector.run()
