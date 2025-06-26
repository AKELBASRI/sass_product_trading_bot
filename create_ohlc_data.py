#!/usr/bin/env python3
"""
Create OHLC Data for Backend
Generates historical candle data that your backend expects
"""

import redis
import json
import pandas as pd
from datetime import datetime, timezone, timedelta
from mt5linux import MetaTrader5
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_ohlc_data():
    print("��️ Creating OHLC Data for Backend")
    print("=" * 40)
    
    # Connect to Redis
    try:
        r = redis.Redis(host='localhost', port=6382, decode_responses=True)
        r.ping()
        print("✅ Redis connected")
    except Exception as e:
        print(f"❌ Redis error: {e}")
        return
    
    # Connect to MT5
    try:
        mt5 = MetaTrader5(host='localhost', port=8001)
        if mt5.initialize():
            account = mt5.account_info()
            print(f"✅ MT5 connected: {account.login}")
        else:
            print("❌ MT5 connection failed")
            return
    except Exception as e:
        print(f"❌ MT5 error: {e}")
        return
    
    # Define symbols and timeframes
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']
    timeframes = {
        '1': mt5.TIMEFRAME_M1,
        '5': mt5.TIMEFRAME_M5,
        '15': mt5.TIMEFRAME_M15,
        '30': mt5.TIMEFRAME_M30,
        '60': mt5.TIMEFRAME_H1,
        '240': mt5.TIMEFRAME_H4,
        '1440': mt5.TIMEFRAME_D1
    }
    
    # Fetch and store OHLC data
    for symbol in symbols:
        print(f"\n📊 Processing {symbol}...")
        
        for tf_str, tf_mt5 in timeframes.items():
            try:
                # Get historical data (last 100 bars)
                rates = mt5.copy_rates_from_pos(symbol, tf_mt5, 0, 100)
                
                if rates is None or len(rates) == 0:
                    print(f"   ⚠️ No data for {symbol} {tf_str}M")
                    continue
                
                # Convert to DataFrame
                df = pd.DataFrame(rates)
                
                # Convert time column to proper datetime
                df['timestamp'] = pd.to_datetime(df['time'], unit='s')
                
                # Rename columns to match backend expectations
                df = df.rename(columns={
                    'tick_volume': 'volume'
                })
                
                # Select only needed columns
                ohlc_df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
                
                # Convert timestamp to ISO format
                ohlc_df['timestamp'] = ohlc_df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')
                
                # Store in Redis as JSON (the format your backend expects)
                key = f"mt5:ohlc:{symbol}:{tf_str}"
                
                # Convert DataFrame to the format your backend expects
                df_dict = ohlc_df.to_dict()
                
                # Store in Redis
                r.set(key, json.dumps(df_dict))
                
                print(f"   ✅ Stored {len(ohlc_df)} candles for {symbol} {tf_str}M")
                
            except Exception as e:
                print(f"   ❌ Error with {symbol} {tf_str}M: {e}")
    
    # Update status
    status_data = {
        'status': 'ohlc_data_created',
        'timestamp': int(datetime.now().timestamp()),
        'last_update': datetime.now(timezone.utc).isoformat(),
        'symbols': symbols,
        'timeframes': list(timeframes.keys()),
        'data_source': 'mt5_historical'
    }
    
    r.set("mt5:ohlc:status", json.dumps(status_data))
    
    # Show what we created
    print(f"\n✅ OHLC Data Creation Complete!")
    ohlc_keys = r.keys("mt5:ohlc:*")
    
    print(f"📈 Created {len(ohlc_keys)} OHLC keys:")
    for key in sorted(ohlc_keys):
        print(f"   {key}")
    
    mt5.shutdown()
    return True

if __name__ == "__main__":
    create_ohlc_data()
