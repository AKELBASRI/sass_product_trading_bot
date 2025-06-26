#!/usr/bin/env python3
"""
Populate Current Data - Add fresh market data
"""

import redis
import json
import time
from datetime import datetime, timezone
from mt5linux import MetaTrader5

def populate_data():
    print("🚀 Populating Fresh MT5 Data")
    print("=" * 35)
    
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
            print(f"✅ MT5 connected: {account.login} - {account.server}")
            print(f"💰 Balance: ${account.balance}")
        else:
            print("❌ MT5 connection failed")
            return
    except Exception as e:
        print(f"❌ MT5 error: {e}")
        return
    
    # Get current data
    print(f"\n📊 Fetching live market data...")
    
    symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD']
    current_time = int(time.time())
    
    for symbol in symbols:
        try:
            # Get tick data
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                spread_pips = round((tick.ask - tick.bid) * 10000, 1)
                print(f"   💱 {symbol}: {tick.bid:.5f}/{tick.ask:.5f} (Spread: {spread_pips} pips)")
                
                # Store as string (JSON)
                tick_data = {
                    'symbol': symbol,
                    'bid': float(tick.bid),
                    'ask': float(tick.ask),
                    'spread_pips': spread_pips,
                    'timestamp': int(tick.time),
                    'collected_at': current_time,
                    'datetime': datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat()
                }
                
                # Store latest tick as JSON string
                r.set(f"mt5:tick:{symbol}:latest", json.dumps(tick_data))
                
                # Also store in a hash for easy field access
                r.hset(f"mt5:hash:{symbol}:latest", mapping={
                    'bid': str(tick.bid),
                    'ask': str(tick.ask),
                    'spread_pips': str(spread_pips),
                    'timestamp': str(tick.time),
                    'symbol': symbol
                })
        
        except Exception as e:
            print(f"   ❌ Error with {symbol}: {e}")
    
    # Update main status
    status_data = {
        'status': 'updated',
        'timestamp': current_time,
        'last_update': datetime.now(timezone.utc).isoformat(),
        'symbols_count': len(symbols),
        'data_source': 'manual_collection'
    }
    
    # Store status as both hash and JSON for compatibility
    r.hset("mt5:status", mapping={
        'status': status_data['status'],
        'timestamp': str(status_data['timestamp']),
        'last_update': status_data['last_update'],
        'symbols_count': str(status_data['symbols_count'])
    })
    
    r.set("mt5:status:json", json.dumps(status_data))
    
    # Show what we created
    print(f"\n✅ Data collection complete!")
    all_keys = r.keys("mt5:*")
    print(f"📈 Total MT5 keys: {len(all_keys)}")
    for key in sorted(all_keys):
        key_type = r.type(key)
        print(f"   {key} ({key_type})")
    
    mt5.shutdown()

if __name__ == "__main__":
    populate_data()
