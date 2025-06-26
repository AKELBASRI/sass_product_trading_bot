#!/usr/bin/env python3
"""
Debug Redis Data Format - Compare what we stored vs what backend expects
"""

import redis
import json
import pandas as pd
import requests

def debug_redis_data():
    print("🔍 Debugging Redis Data Format")
    print("=" * 50)
    
    # Connect to Redis
    r = redis.Redis(host='localhost', port=6382, decode_responses=True)
    
    # Check what keys exist
    all_keys = r.keys("*")
    ohlc_keys = [k for k in all_keys if k.startswith("mt5:ohlc:")]
    
    print(f"📊 Total keys: {len(all_keys)}")
    print(f"📈 OHLC keys: {len(ohlc_keys)}")
    
    if not ohlc_keys:
        print("❌ No OHLC data found!")
        return
    
    # Check a sample key
    sample_key = "mt5:ohlc:EURUSD:15"
    if sample_key in ohlc_keys:
        print(f"\n🔬 Examining key: {sample_key}")
        
        # Get raw data
        raw_data = r.get(sample_key)
        print(f"Raw data length: {len(raw_data)} characters")
        print(f"Raw data sample: {raw_data[:200]}...")
        
        try:
            # Parse as JSON
            data = json.loads(raw_data)
            print(f"\n📋 Data structure:")
            print(f"Type: {type(data)}")
            print(f"Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict):
                        print(f"  {key}: dict with {len(value)} items")
                        sample_items = list(value.items())[:3]
                        print(f"    Sample: {sample_items}")
                    else:
                        print(f"  {key}: {type(value)} - {str(value)[:50]}")
            
            # Test backend parsing
            print(f"\n🧪 Testing Backend Logic:")
            test_backend_parsing(data)
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
    
    # Test API directly
    print(f"\n🌐 Testing API Response:")
    try:
        response = requests.get('http://localhost:8009/debug-raw/EURUSD?timeframe=15')
        if response.status_code == 200:
            debug_data = response.json()
            print(f"Debug response: {json.dumps(debug_data, indent=2)}")
        else:
            print(f"Debug endpoint not available: {response.status_code}")
    except:
        print("Debug endpoint not accessible")

def test_backend_parsing(data):
    """Simulate what the backend does to parse data"""
    try:
        # This mimics your backend's get_ohlc_data method
        if 'index' in data:
            indices = data['index']
            close_data = data.get('close', {})
            open_data = data.get('open', {})
            high_data = data.get('high', {})
            low_data = data.get('low', {})
            volume_data = data.get('volume', {})
            
            print(f"✅ Found expected structure:")
            print(f"  - Index type: {type(indices)}, length: {len(indices) if hasattr(indices, '__len__') else 'N/A'}")
            print(f"  - Close data type: {type(close_data)}, length: {len(close_data)}")
            print(f"  - Sample close keys: {list(close_data.keys())[:5]}")
            
            # Try to build a candle
            candles = []
            for idx_key in sorted(close_data.keys(), key=int)[:3]:  # Just first 3
                try:
                    candle = {
                        'timestamp': indices[int(idx_key)] if int(idx_key) < len(indices) else f"2025-06-25T{int(idx_key):02d}:00:00",
                        'open': float(open_data.get(idx_key, 0)),
                        'high': float(high_data.get(idx_key, 0)),
                        'low': float(low_data.get(idx_key, 0)),
                        'close': float(close_data.get(idx_key, 0)),
                        'volume': int(volume_data.get(idx_key, 0))
                    }
                    candles.append(candle)
                    print(f"  ✅ Candle {idx_key}: {candle}")
                except Exception as e:
                    print(f"  ❌ Error building candle {idx_key}: {e}")
            
            print(f"✅ Successfully built {len(candles)} candles")
            
        else:
            print(f"❌ No 'index' key found. Available keys: {list(data.keys())}")
            
    except Exception as e:
        print(f"❌ Backend parsing simulation failed: {e}")

def fix_data_format():
    """Fix the data format to match what backend expects"""
    print(f"\n🔧 Attempting to fix data format...")
    
    # Connect to services
    r = redis.Redis(host='localhost', port=6382, decode_responses=True)
    
    try:
        from mt5linux import MetaTrader5
        import pandas as pd
        
        # Connect to MT5
        mt5 = MetaTrader5(host='localhost', port=8001)
        if not mt5.initialize():
            print("❌ Failed to connect to MT5")
            return False
        
        print("✅ Connected to MT5")
        
        # Get fresh data for EURUSD
        rates = mt5.copy_rates_from_pos("EURUSD", MetaTrader5.TIMEFRAME_M15, 0, 100)
        
        if rates is None:
            print("❌ No data from MT5")
            return False
        
        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.rename(columns={'time': 'timestamp', 'tick_volume': 'volume'})
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        print(f"✅ Created DataFrame with {len(df)} rows")
        print(f"DataFrame columns: {df.columns.tolist()}")
        print(f"Sample row: {df.iloc[0].to_dict()}")
        
        # Convert to the EXACT format your backend expects
        df_dict = df.to_dict()
        
        print(f"\n📋 DataFrame dict structure:")
        for key, value in df_dict.items():
            print(f"  {key}: {type(value)} with {len(value)} items")
            if key == 'timestamp':
                sample_values = list(value.values())[:3]
                print(f"    Sample values: {sample_values}")
        
        # Store in Redis
        key = "mt5:ohlc:EURUSD:15"
        r.setex(key, 3600, json.dumps(df_dict, default=str))
        
        print(f"✅ Stored fixed data in {key}")
        
        # Test immediately
        print(f"\n🧪 Testing fixed data...")
        response = requests.get('http://localhost:8009/ohlc/EURUSD?limit=5')
        
        if response.status_code == 200:
            data = response.json()
            if data['count'] > 0:
                print(f"✅ SUCCESS! Got {data['count']} bars")
                print(f"Latest price: {data['data'][-1]['close']}")
                return True
            else:
                print(f"❌ Still no data. Response: {data}")
        else:
            print(f"❌ API error: {response.status_code}")
        
        mt5.shutdown()
        
    except Exception as e:
        print(f"❌ Fix attempt failed: {e}")
        import traceback
        traceback.print_exc()
    
    return False

if __name__ == "__main__":
    debug_redis_data()
    
    print("\n" + "=" * 50)
    print("🛠️ Would you like to try fixing the data format? (y/n)")
    
    choice = input().strip().lower()
    if choice == 'y':
        if fix_data_format():
            print("\n🎉 Data format fixed! Try your API calls now.")
        else:
            print("\n😞 Fix attempt unsuccessful. Let's debug further.")
    else:
        print("\n👍 Debug complete. Check the output above for clues.")