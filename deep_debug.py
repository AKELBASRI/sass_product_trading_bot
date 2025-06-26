#!/usr/bin/env python3
"""
Deep Debug - Simulate exact backend parsing logic
"""

import redis
import json

def simulate_backend_parsing():
    print("🔬 Deep Debug - Simulating Backend Parsing")
    print("=" * 50)
    
    # Connect to Redis
    r = redis.Redis(host='localhost', port=6382, decode_responses=True)
    
    # Get the exact data the backend is trying to parse
    key = "mt5:ohlc:EURUSD:15"
    data_str = r.get(key)
    
    if not data_str:
        print("❌ No data found")
        return
    
    print(f"✅ Found data for {key}")
    
    try:
        # Parse JSON exactly like the backend
        df_dict = json.loads(data_str)
        print(f"📋 Loaded DataFrame dict with keys: {list(df_dict.keys())}")
        
        # Check for timestamp data (this should exist now)
        if 'timestamp' in df_dict:
            print("✅ Found 'timestamp' key")
            
            timestamp_data = df_dict['timestamp']
            close_data = df_dict.get('close', {})
            open_data = df_dict.get('open', {})
            high_data = df_dict.get('high', {})
            low_data = df_dict.get('low', {})
            volume_data = df_dict.get('volume', {})
            
            print(f"📊 Data sizes:")
            print(f"  - timestamp_data: {len(timestamp_data)} items")
            print(f"  - close_data: {len(close_data)} items")
            print(f"  - Keys type: {type(list(timestamp_data.keys())[0])}")
            
            # Show sample keys
            sample_keys = list(timestamp_data.keys())[:5]
            print(f"  - Sample keys: {sample_keys}")
            
            # Try the exact parsing logic from backend
            candles = []
            
            print(f"\n🔄 Processing candles...")
            
            for idx_key in sorted(timestamp_data.keys(), key=int):
                try:
                    candle = {
                        'timestamp': timestamp_data.get(idx_key, f"2025-06-25T{int(idx_key):02d}:00:00"),
                        'open': float(open_data.get(idx_key, 0)),
                        'high': float(high_data.get(idx_key, 0)),
                        'low': float(low_data.get(idx_key, 0)),
                        'close': float(close_data.get(idx_key, 0)),
                        'volume': int(volume_data.get(idx_key, 0))
                    }
                    candles.append(candle)
                    
                    if len(candles) <= 3:  # Show first 3
                        print(f"  ✅ Candle {idx_key}: {candle}")
                    
                except (ValueError, KeyError) as e:
                    print(f"  ❌ Error with candle {idx_key}: {e}")
                    # Show what we got
                    print(f"     timestamp_data.get('{idx_key}'): {timestamp_data.get(idx_key)}")
                    print(f"     close_data.get('{idx_key}'): {close_data.get(idx_key)}")
                    break
            
            print(f"\n📈 Total candles created: {len(candles)}")
            
            if len(candles) == 0:
                print("❌ No candles were created! Let's debug why...")
                
                # Check a specific key
                test_key = list(timestamp_data.keys())[0]
                print(f"\n🔍 Debugging key '{test_key}':")
                print(f"  - timestamp_data['{test_key}'] = {timestamp_data.get(test_key)}")
                print(f"  - open_data['{test_key}'] = {open_data.get(test_key)}")
                print(f"  - close_data['{test_key}'] = {close_data.get(test_key)}")
                
                # Try to create one candle manually
                try:
                    test_candle = {
                        'timestamp': timestamp_data.get(test_key),
                        'open': float(open_data.get(test_key, 0)),
                        'high': float(high_data.get(test_key, 0)),
                        'low': float(low_data.get(test_key, 0)),
                        'close': float(close_data.get(test_key, 0)),
                        'volume': int(volume_data.get(test_key, 0))
                    }
                    print(f"  ✅ Manual candle creation worked: {test_candle}")
                    
                except Exception as e:
                    print(f"  ❌ Manual candle creation failed: {e}")
                    print(f"  ❌ Error details: {type(e).__name__}: {str(e)}")
            
            else:
                # Apply limit like backend does
                limit = 5
                if limit > 0 and len(candles) > limit:
                    candles = candles[-limit:]
                
                result = {
                    "symbol": "EURUSD",
                    "timeframe": "15",
                    "data": candles,
                    "count": len(candles),
                    "key_type": "dataframe_json_fixed",
                    "total_available": len(df_dict.get('close', {}))
                }
                
                print(f"\n✅ Backend would return: {result['count']} candles")
                print(f"📋 First candle: {result['data'][0] if result['data'] else 'None'}")
        
        else:
            print("❌ No 'timestamp' key found")
            print(f"Available keys: {list(df_dict.keys())}")
    
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        import traceback
        traceback.print_exc()

def check_backend_code():
    """Check what's actually in the backend code now"""
    print(f"\n📝 Checking current backend code...")
    
    try:
        with open('backend_service.py', 'r') as f:
            content = f.read()
        
        # Check if our fixes are there
        if "if 'timestamp' in df_dict:" in content:
            print("✅ Backend has 'timestamp' check")
        else:
            print("❌ Backend still has 'index' check")
        
        if "timestamp_data.get(idx_key" in content:
            print("✅ Backend uses timestamp_data.get()")
        else:
            print("❌ Backend still uses indices[int(idx_key)]")
        
        if "for idx_key in sorted(timestamp_data.keys(), key=int):" in content:
            print("✅ Backend iterates over timestamp_data.keys()")
        else:
            print("❌ Backend still iterates over close_data.keys()")
            
    except Exception as e:
        print(f"❌ Error checking backend code: {e}")

if __name__ == "__main__":
    simulate_backend_parsing()
    check_backend_code()