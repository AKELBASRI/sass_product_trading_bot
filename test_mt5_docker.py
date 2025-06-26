# test_mt5_docker.py - Updated test script
#!/usr/bin/env python3
"""
Test MT5 Docker connection
"""

import redis
import json
import time
import sys

# Connect to Redis
r = redis.Redis(host='localhost', port=6381, decode_responses=True)

print("Checking MT5 connection status...")

# Check MT5 status
status = r.hgetall('mt5:status')
if status:
    print("\n? MT5 Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")
else:
    print("\n? MT5 not connected yet. Please wait...")
    sys.exit(1)

# Get account info
account = r.hgetall('mt5:account')
if account:
    print("\n? Account Info:")
    for key, value in account.items():
        print(f"  {key}: {value}")

# Get latest EURUSD tick
tick = r.hgetall('mt5:tick:EURUSD')
if tick:
    print("\n? EURUSD Latest Tick:")
    for key, value in tick.items():
        print(f"  {key}: {value}")
else:
    print("\n? No EURUSD tick data available yet")

# Check OHLC data
ohlc_key = 'mt5:ohlc:EURUSD:15'
ohlc_data = r.get(ohlc_key)
if ohlc_data:
    data = json.loads(ohlc_data)
    print(f"\n? EURUSD M15 OHLC Data: {len(data.get('time', []))} bars available")
else:
    print("\n? No OHLC data available yet")

# Test placing an order (BE CAREFUL - this will place a real order!)
if False:  # Change to True to test order placement
    print("\n?? Testing order placement...")
    command = {
        'id': '12345',
        'action': 'place_order',
        'symbol': 'EURUSD',
        'order_type': 'BUY',
        'volume': 0.01,
        'sl': None,
        'tp': None,
        'comment': 'Test order from Docker'
    }
    
    r.publish('mt5:commands', json.dumps(command))
    print("Order command sent! Check logs for result.")

print("\n? Connection test completed!")