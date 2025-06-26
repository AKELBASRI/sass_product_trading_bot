#!/usr/bin/env python3
"""
Real MT5 Connector - Fetches real data from MT5 and stores in Redis
"""

import json
import logging
import time
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import redis
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RealMT5Connector:
    def __init__(self):
        """Initialize the real MT5 connector"""
        self.redis_client = None
        self.mt5 = None
        self.mt5_connected = False
        self.redis_connected = False
        
        # Trading symbols to fetch
        self.symbols = [
            "EURUSD", "GBPUSD", "USDJPY", "USDCHF", 
            "USDCAD", "AUDUSD", "NZDUSD", "EURJPY",
            "EURGBP", "GBPJPY"
        ]
        
        # Timeframes to fetch (MT5 constants)
        self.timeframes = {
            "1": None,   # Will be set after MT5 import
            "5": None,
            "15": None,
            "30": None,
            "60": None,  # 1H
            "240": None, # 4H
            "1440": None # 1D
        }
        
        self.running = False
        
    def connect_redis(self):
        """Connect to Redis"""
        try:
            redis_host = os.getenv('REDIS_HOST', 'redis')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            
            logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")
            
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=True,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("✅ Redis connection successful")
            self.redis_connected = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.redis_connected = False
            return False
    
    def connect_mt5(self):
        """Connect to MT5"""
        try:
            # Import MT5Linux
            try:
                from mt5linux import MetaTrader5
                logger.info("✅ mt5linux imported successfully")
            except ImportError as e:
                logger.error(f"❌ Failed to import mt5linux: {e}")
                logger.error("Install with: pip install mt5linux")
                return False
            
            # Connect to MT5
            mt5_host = os.getenv('MT5_HOST', 'mt5-real')
            mt5_port = int(os.getenv('MT5_PORT', 8001))
            
            logger.info(f"Connecting to MT5 at {mt5_host}:{mt5_port}")
            
            self.mt5 = MetaTrader5(host=mt5_host, port=mt5_port)
            
            # Initialize MT5
            if not self.mt5.initialize():
                logger.error("❌ MT5 initialization failed")
                return False
            
            # Setup timeframes after successful connection
            self.timeframes = {
                "1": self.mt5.TIMEFRAME_M1,
                "5": self.mt5.TIMEFRAME_M5,
                "15": self.mt5.TIMEFRAME_M15,
                "30": self.mt5.TIMEFRAME_M30,
                "60": self.mt5.TIMEFRAME_H1,
                "240": self.mt5.TIMEFRAME_H4,
                "1440": self.mt5.TIMEFRAME_D1
            }
            
            # Get account info
            try:
                account = self.mt5.account_info()
                if account:
                    logger.info(f"✅ MT5 connected - Account: {account.login} ({account.server})")
                    logger.info(f"Balance: {account.balance} {account.currency}")
                else:
                    logger.warning("⚠️ MT5 connected but no account info")
                    
                # Get version
                version = self.mt5.version()
                logger.info(f"MT5 Version: {version}")
                
            except Exception as e:
                logger.warning(f"Account info error: {e}")
            
            self.mt5_connected = True
            logger.info("✅ MT5 connection successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ MT5 connection failed: {e}")
            self.mt5_connected = False
            return False
    
    def fetch_ohlc_data(self, symbol: str, timeframe_str: str, count: int = 1000) -> Optional[pd.DataFrame]:
        """Fetch OHLC data from MT5"""
        try:
            if not self.mt5_connected:
                logger.error("MT5 not connected")
                return None
            
            timeframe = self.timeframes.get(timeframe_str)
            if timeframe is None:
                logger.error(f"Invalid timeframe: {timeframe_str}")
                return None
            
            # Fetch rates
            rates = self.mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            
            if rates is None or len(rates) == 0:
                logger.warning(f"No data for {symbol} {timeframe_str}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(rates)
            
            # Convert time to readable format
            df['timestamp'] = pd.to_datetime(df['time'], unit='s')
            
            # Select and rename columns
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'tick_volume']].copy()
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
            
            # Ensure proper data types
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            df['volume'] = df['volume'].astype(int)
            
            logger.info(f"✅ Fetched {len(df)} bars for {symbol} {timeframe_str}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error fetching {symbol} {timeframe_str}: {e}")
            return None
    
    def store_ohlc_data(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """Store OHLC data in Redis"""
        try:
            if not self.redis_connected or df is None or df.empty:
                return False
            
            # Convert DataFrame to the format your backend expects
            # Your backend expects DataFrame.to_json() format
            data_dict = {
                'index': df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S').tolist(),
                'open': {str(i): float(val) for i, val in enumerate(df['open'])},
                'high': {str(i): float(val) for i, val in enumerate(df['high'])},
                'low': {str(i): float(val) for i, val in enumerate(df['low'])},
                'close': {str(i): float(val) for i, val in enumerate(df['close'])},
                'volume': {str(i): int(val) for i, val in enumerate(df['volume'])}
            }
            
            # Store in Redis
            key = f"mt5:ohlc:{symbol}:{timeframe}"
            self.redis_client.set(key, json.dumps(data_dict))
            
            # Store metadata
            metadata = {
                'symbol': symbol,
                'timeframe': timeframe,
                'count': len(df),
                'last_update': datetime.now().isoformat(),
                'latest_time': df['timestamp'].iloc[-1].isoformat(),
                'latest_price': float(df['close'].iloc[-1])
            }
            
            meta_key = f"mt5:meta:{symbol}:{timeframe}"
            self.redis_client.set(meta_key, json.dumps(metadata))
            
            logger.info(f"✅ Stored {len(df)} bars for {symbol} {timeframe} in Redis")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing {symbol} {timeframe}: {e}")
            return False
    
    def fetch_and_store_all(self):
        """Fetch and store data for all symbols and timeframes"""
        success_count = 0
        total_count = 0
        
        for symbol in self.symbols:
            for timeframe in self.timeframes.keys():
                total_count += 1
                
                try:
                    # Fetch data
                    df = self.fetch_ohlc_data(symbol, timeframe, count=1000)
                    
                    if df is not None and not df.empty:
                        # Store in Redis
                        if self.store_ohlc_data(symbol, timeframe, df):
                            success_count += 1
                    
                    # Small delay to avoid overwhelming MT5
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error processing {symbol} {timeframe}: {e}")
        
        logger.info(f"✅ Completed: {success_count}/{total_count} successful")
        return success_count, total_count
    
    def store_system_status(self):
        """Store system status in Redis"""
        try:
            status = {
                'mt5_connected': self.mt5_connected,
                'redis_connected': self.redis_connected,
                'running': self.running,
                'last_update': datetime.now().isoformat(),
                'symbols': self.symbols,
                'timeframes': list(self.timeframes.keys())
            }
            
            self.redis_client.set('mt5:system:status', json.dumps(status))
            
        except Exception as e:
            logger.error(f"Error storing system status: {e}")
    
    def run_once(self):
        """Run one complete data fetch cycle"""
        logger.info("🔄 Starting data fetch cycle...")
        
        # Connect to services
        if not self.redis_connected:
            if not self.connect_redis():
                return False
        
        if not self.mt5_connected:
            if not self.connect_mt5():
                return False
        
        # Fetch and store all data
        success, total = self.fetch_and_store_all()
        
        # Store system status
        self.store_system_status()
        
        logger.info(f"✅ Data fetch cycle completed: {success}/{total}")
        return success > 0
    
    def run_continuous(self, interval_seconds: int = 60):
        """Run continuous data fetching"""
        self.running = True
        logger.info(f"🚀 Starting continuous MT5 data fetching (interval: {interval_seconds}s)")
        
        while self.running:
            try:
                self.run_once()
                
                # Wait for next cycle
                logger.info(f"⏰ Waiting {interval_seconds} seconds for next cycle...")
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("👋 Received stop signal")
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                time.sleep(10)  # Wait before retrying
        
        self.stop()
    
    def stop(self):
        """Stop the connector"""
        self.running = False
        
        if self.mt5_connected and self.mt5:
            try:
                self.mt5.shutdown()
                logger.info("✅ MT5 connection closed")
            except:
                pass
        
        logger.info("👋 MT5 Connector stopped")
    
    def test_connection(self):
        """Test all connections"""
        logger.info("🧪 Testing connections...")
        
        # Test Redis
        redis_ok = self.connect_redis()
        
        # Test MT5
        mt5_ok = self.connect_mt5()
        
        if redis_ok and mt5_ok:
            logger.info("🎉 All connections successful!")
            
            # Test fetching one symbol
            logger.info("🧪 Testing data fetch...")
            df = self.fetch_ohlc_data("EURUSD", "15", count=10)
            
            if df is not None:
                logger.info(f"✅ Sample data: {len(df)} bars")
                logger.info(f"Latest EURUSD: {df['close'].iloc[-1]:.5f}")
                
                # Test storing
                if self.store_ohlc_data("EURUSD", "15", df):
                    logger.info("✅ Data storage test successful")
                    return True
        
        return False

def main():
    """Main function"""
    print("🚀 Real MT5 Connector Starting...")
    
    connector = RealMT5Connector()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "test":
            print("🧪 Running connection test...")
            success = connector.test_connection()
            print("✅ Test completed successfully!" if success else "❌ Test failed!")
            return
        
        elif command == "once":
            print("🔄 Running single data fetch...")
            success = connector.run_once()
            print("✅ Fetch completed!" if success else "❌ Fetch failed!")
            return
    
    # Default: run continuous
    try:
        # Get update interval from environment
        interval = int(os.getenv('UPDATE_INTERVAL', 60))
        connector.run_continuous(interval)
        
    except KeyboardInterrupt:
        print("\n👋 Stopping...")
    finally:
        connector.stop()

if __name__ == "__main__":
    main()