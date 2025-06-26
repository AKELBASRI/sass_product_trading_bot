#!/usr/bin/env python3
"""
MT5 Data Connector - Uses host MT5 connection to populate Redis
"""

import os
import time
import json
import logging
import sys
import subprocess
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_host_script():
    """Run the data fetching script on the host"""
    host_script = """
import json
import time
import redis
import pandas as pd
from mt5linux import MetaTrader5
from datetime import datetime

# Connect to Redis (from container perspective)
r = redis.Redis(host='redis', port=6379, decode_responses=True)

# Connect to MT5
mt5 = MetaTrader5(host='mt5-real', port=8001)
if not mt5.initialize():
    print("Failed to connect to MT5")
    exit(1)

print("Connected to MT5")

# Symbols and timeframes
symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD']
timeframes = {
    '1': mt5.TIMEFRAME_M1,
    '5': mt5.TIMEFRAME_M5,
    '15': mt5.TIMEFRAME_M15,
    '30': mt5.TIMEFRAME_M30,
    '60': mt5.TIMEFRAME_H1,
    '240': mt5.TIMEFRAME_H4,
    '1440': mt5.TIMEFRAME_D1
}

success_count = 0
total_count = len(symbols) * len(timeframes)

for symbol in symbols:
    for tf_key, tf_value in timeframes.items():
        try:
            # Fetch data
            rates = mt5.copy_rates_from_pos(symbol, tf_value, 0, 1000)
            
            if rates is not None and len(rates) > 0:
                # Convert to DataFrame
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df = df.rename(columns={'time': 'timestamp', 'tick_volume': 'volume'})
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')
                
                # Store in Redis
                key = f"mt5:ohlc:{symbol}:{tf_key}"
                df_dict = df.to_dict()
                r.setex(key, 86400, json.dumps(df_dict, default=str))
                
                print(f"Stored {len(df)} bars for {symbol} {tf_key}")
                success_count += 1
            
            time.sleep(0.1)  # Small delay
            
        except Exception as e:
            print(f"Error processing {symbol} {tf_key}: {e}")

mt5.shutdown()
print(f"Completed: {success_count}/{total_count} successful")

# Update status
status_data = {
    'status': 'running',
    'timestamp': datetime.now().isoformat(),
    'message': f'Data updated: {success_count}/{total_count} successful',
    'symbols': symbols,
    'timeframes': list(timeframes.keys())
}
r.setex('mt5:connector:status', 300, json.dumps(status_data))
"""
    
    # Save to temp file and run on host
    with open('/tmp/mt5_fetch.py', 'w') as f:
        f.write(host_script)
    
    return host_script

class MT5DataConnector:
    def __init__(self):
        self.update_interval = int(os.getenv('UPDATE_INTERVAL', 300))  # 5 minutes
        self.running = False
    
    def run(self):
        """Main loop - periodically trigger host script"""
        logger.info("🚀 Starting MT5 Data Connector (Host Mode)")
        self.running = True
        
        host_script = run_host_script()
        
        try:
            while self.running:
                logger.info("🔄 Triggering data fetch on host...")
                
                try:
                    # Execute the script on the host via docker exec
                    cmd = [
                        'docker', 'exec', '-i', 'mt5-real',
                        'python3', '-c', host_script
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    
                    if result.returncode == 0:
                        logger.info("✅ Data fetch completed successfully")
                        logger.info(result.stdout)
                    else:
                        logger.error(f"❌ Data fetch failed: {result.stderr}")
                
                except subprocess.TimeoutExpired:
                    logger.error("❌ Data fetch timed out")
                except Exception as e:
                    logger.error(f"❌ Error executing data fetch: {e}")
                
                logger.info(f"💤 Sleeping for {self.update_interval} seconds...")
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            logger.info("🛑 Received stop signal")
        finally:
            self.running = False
            logger.info("🛑 MT5 Data Connector stopped")

if __name__ == "__main__":
    connector = MT5DataConnector()
    connector.run()
