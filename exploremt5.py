#!/usr/bin/env python3
"""
Quick Test - Check your current setup
"""

import requests
import redis
import json

def test_current_setup():
    print("🧪 Testing Current Setup")
    print("=" * 40)
    
    # Test Redis
    print("\n🔍 Testing Redis...")
    try:
        r = redis.Redis(host='localhost', port=6382, decode_responses=True)
        r.ping()
        print("✅ Redis is accessible")
        
        # Check existing keys
        keys = r.keys("*")
        mt5_keys = [k for k in keys if k.startswith("mt5:")]
        print(f"Total keys: {len(keys)}")
        print(f"MT5 keys: {len(mt5_keys)}")
        
        if mt5_keys:
            print("✅ MT5 data already exists!")
            for key in mt5_keys[:5]:
                print(f"  - {key}")
        else:
            print("⚠️ No MT5 data found yet")
            
    except Exception as e:
        print(f"❌ Redis error: {e}")
    
    # Test Backend
    print("\n🔍 Testing Backend...")
    try:
        response = requests.get("http://localhost:8009/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print("✅ Backend is running")
            print(f"Status: {health.get('status')}")
            print(f"Redis connected: {health.get('components', {}).get('redis')}")
            print(f"MT5 connected: {health.get('components', {}).get('mt5')}")
        else:
            print(f"❌ Backend returned {response.status_code}")
    except Exception as e:
        print(f"❌ Backend error: {e}")
    
    # Test MT5 Container
    print("\n🔍 Testing MT5 Container...")
    try:
        import subprocess
        result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
        if 'mt5-real' in result.stdout:
            print("✅ MT5 container is running")
        else:
            print("❌ MT5 container not found")
    except Exception as e:
        print(f"❌ Docker check error: {e}")
    
    # Test MT5 Connection
    print("\n🔍 Testing MT5 Connection...")
    try:
        from mt5linux import MetaTrader5
        mt5 = MetaTrader5(host='localhost', port=8001)
        if mt5.initialize():
            print("✅ MT5 connection successful")
            account = mt5.account_info()
            if account:
                print(f"Account: {account.login} - {account.server}")
                print(f"Balance: {account.balance}")
            
            # Test data fetch
            rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_M15, 0, 5)
            if rates is not None:
                print(f"✅ Can fetch data: {len(rates)} bars")
                print(f"Latest EURUSD: {rates[-1]['close']:.5f}")
            else:
                print("⚠️ No market data available")
            
            mt5.shutdown()
        else:
            print("❌ MT5 initialization failed")
    except ImportError:
        print("❌ mt5linux not installed")
        print("Run: pip install mt5linux")
    except Exception as e:
        print(f"❌ MT5 error: {e}")

if __name__ == "__main__":
    test_current_setup()
    
    print("\n" + "=" * 40)
    print("🚀 To integrate MT5 with Redis:")
    print("python simple_mt5_integration.py")