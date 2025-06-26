#!/usr/bin/env python3
"""
Debug Stream Issues - Find out why stream data isn't being created
"""

import redis
import json
import requests
from datetime import datetime
from mt5linux import MetaTrader5

def debug_streaming_issues():
    print("🔍 Debug Stream Issues")
    print("=" * 40)
    
    # 1. Check Redis connection
    try:
        r = redis.Redis(host='localhost', port=6382, decode_responses=True)
        r.ping()
        print("✅ Redis connected")
    except Exception as e:
        print(f"❌ Redis error: {e}")
        return
    
    # 2. Check streaming server
    try:
        response = requests.get("http://localhost:8010/status", timeout=5)
        status = response.json()
        print(f"✅ Streaming server running")
        print(f"   Streaming: {status['streaming']}")
        print(f"   Clients: {status['clients']}")
    except Exception as e:
        print(f"❌ Streaming server error: {e}")
        return
    
    # 3. Check MT5 connection directly
    print(f"\n🔌 Testing MT5 connection...")
    try:
        mt5 = MetaTrader5(host='localhost', port=8001)
        if mt5.initialize():
            print("✅ MT5 connection works")
            
            # Test getting tick data
            symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']
            for symbol in symbols:
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    print(f"   ✅ {symbol}: {tick.bid:.5f}/{tick.ask:.5f}")
                else:
                    print(f"   ❌ {symbol}: No tick data")
            
            mt5.shutdown()
        else:
            print("❌ MT5 initialization failed")
            return
    except Exception as e:
        print(f"❌ MT5 error: {e}")
        return
    
    # 4. Check existing Redis keys
    print(f"\n📊 Redis key analysis...")
    all_keys = r.keys("mt5:*")
    stream_keys = [k for k in all_keys if k.startswith("mt5:stream:")]
    tick_keys = [k for k in all_keys if k.startswith("mt5:tick:")]
    hash_keys = [k for k in all_keys if k.startswith("mt5:hash:")]
    
    print(f"   Total MT5 keys: {len(all_keys)}")
    print(f"   Stream keys: {len(stream_keys)}")
    print(f"   Tick keys: {len(tick_keys)}")
    print(f"   Hash keys: {len(hash_keys)}")
    
    if stream_keys:
        print(f"   ✅ Stream keys found:")
        for key in stream_keys[:5]:
            print(f"      {key}")
    else:
        print(f"   ❌ No stream keys - this is the problem!")
    
    # 5. Test manual stream data creation
    print(f"\n🧪 Testing manual stream data creation...")
    try:
        mt5 = MetaTrader5(host='localhost', port=8001)
        if mt5.initialize():
            symbol = 'EURUSD'
            tick = mt5.symbol_info_tick(symbol)
            
            if tick:
                # Create stream data manually
                stream_data = {
                    'symbol': symbol,
                    'bid': float(tick.bid),
                    'ask': float(tick.ask),
                    'spread_pips': round((tick.ask - tick.bid) * 10000, 1),
                    'timestamp': int(tick.time),
                    'price_change': 0.0,
                    'price_change_pct': 0.0,
                    'trend': 'neutral'
                }
                
                # Store it
                stream_key = f"mt5:stream:{symbol}:latest"
                r.set(stream_key, json.dumps(stream_data), ex=60)
                
                # Verify it was stored
                stored_data = r.get(stream_key)
                if stored_data:
                    print(f"   ✅ Successfully created stream data for {symbol}")
                    print(f"   📊 {stream_data}")
                else:
                    print(f"   ❌ Failed to store stream data")
            
            mt5.shutdown()
    except Exception as e:
        print(f"   ❌ Manual test error: {e}")
    
    # 6. Check if streaming function is actually running
    print(f"\n🔄 Stream monitoring test...")
    print("   Watching for new stream keys (10 seconds)...")
    
    initial_stream_keys = set(r.keys("mt5:stream:*"))
    
    import time
    time.sleep(10)
    
    final_stream_keys = set(r.keys("mt5:stream:*"))
    new_keys = final_stream_keys - initial_stream_keys
    
    if new_keys:
        print(f"   ✅ New stream keys created: {len(new_keys)}")
        for key in new_keys:
            print(f"      {key}")
    else:
        print(f"   ❌ No new stream keys created in 10 seconds")
        print(f"   💡 The streaming function might not be working")

def fix_streaming():
    """Create a simple fix for streaming"""
    print(f"\n🔧 Quick Fix: Manual Stream Creator")
    print("=" * 40)
    
    try:
        r = redis.Redis(host='localhost', port=6382, decode_responses=True)
        mt5 = MetaTrader5(host='localhost', port=8001)
        
        if not mt5.initialize():
            print("❌ MT5 connection failed")
            return
        
        symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD']
        last_prices = {}
        
        print("🚀 Creating stream data for 30 seconds...")
        
        for i in range(30):  # Run for 30 seconds
            for symbol in symbols:
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    current_price = tick.bid
                    last_price = last_prices.get(symbol, current_price)
                    price_change = current_price - last_price
                    price_change_pct = (price_change / last_price * 100) if last_price != 0 else 0
                    
                    stream_data = {
                        'symbol': symbol,
                        'bid': float(tick.bid),
                        'ask': float(tick.ask),
                        'spread_pips': round((tick.ask - tick.bid) * 10000, 1),
                        'timestamp': int(tick.time),
                        'price_change': round(price_change, 5),
                        'price_change_pct': round(price_change_pct, 4),
                        'trend': "up" if price_change > 0 else "down" if price_change < 0 else "neutral"
                    }
                    
                    # Store stream data
                    stream_key = f"mt5:stream:{symbol}:latest"
                    r.set(stream_key, json.dumps(stream_data), ex=60)
                    
                    last_prices[symbol] = current_price
                    
                    print(f"📊 {symbol}: {tick.bid:.5f}/{tick.ask:.5f} ({stream_data['trend']})")
            
            print(f"⏱️ Iteration {i+1}/30")
            time.sleep(1)
        
        mt5.shutdown()
        print(f"✅ Stream data creation complete!")
        
        # Show created keys
        stream_keys = r.keys("mt5:stream:*")
        print(f"📈 Created {len(stream_keys)} stream keys:")
        for key in stream_keys:
            print(f"   {key}")
            
    except Exception as e:
        print(f"❌ Fix failed: {e}")

if __name__ == "__main__":
    debug_streaming_issues()
    
    print(f"\n" + "=" * 50)
    print("🔧 Want to run the quick fix? (y/n)")
    choice = input().lower().strip()
    
    if choice == 'y':
        fix_streaming()
    else:
        print("💡 To fix manually:")
        print("   1. Check websocket_streamer.py logs")
        print("   2. Restart the streaming server")
        print("   3. Or run the fix function")