#!/usr/bin/env python3
"""
Test Script - Verify MT5 data is flowing to Redis
"""

import json
import time
import redis
import requests
from datetime import datetime

class MT5RedisTest:
    def __init__(self):
        # Connect to Redis
        self.redis_client = redis.Redis(
            host='localhost', 
            port=6382,  # External port from docker-compose
            decode_responses=True
        )
        
        # Backend API URL
        self.backend_url = "http://localhost:8009"
    
    def test_redis_connection(self):
        """Test Redis connection"""
        print("🔍 Testing Redis connection...")
        try:
            self.redis_client.ping()
            print("✅ Redis connection successful")
            return True
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            return False
    
    def check_redis_keys(self):
        """Check what keys are in Redis"""
        print("\n🔍 Checking Redis keys...")
        try:
            all_keys = self.redis_client.keys("*")
            mt5_keys = [k for k in all_keys if k.startswith("mt5:")]
            ohlc_keys = [k for k in all_keys if "mt5:ohlc" in k]
            
            print(f"Total keys: {len(all_keys)}")
            print(f"MT5 keys: {len(mt5_keys)}")
            print(f"OHLC keys: {len(ohlc_keys)}")
            
            if ohlc_keys:
                print("✅ MT5 OHLC data found!")
                print("Sample keys:")
                for key in ohlc_keys[:5]:
                    print(f"  - {key}")
            else:
                print("⚠️ No MT5 OHLC data found")
            
            return len(ohlc_keys) > 0
            
        except Exception as e:
            print(f"❌ Error checking keys: {e}")
            return False
    
    def check_sample_data(self):
        """Check sample OHLC data"""
        print("\n🔍 Checking sample OHLC data...")
        try:
            # Get OHLC keys
            ohlc_keys = self.redis_client.keys("mt5:ohlc:*")
            
            if not ohlc_keys:
                print("❌ No OHLC data found")
                return False
            
            # Test first key
            sample_key = ohlc_keys[0]
            print(f"Testing key: {sample_key}")
            
            data_str = self.redis_client.get(sample_key)
            
            if not data_str:
                print("❌ No data in key")
                return False
            
            # Parse JSON
            data = json.loads(data_str)
            
            print(f"✅ Data structure found:")
            print(f"  - Keys: {list(data.keys())}")
            
            if 'close' in data:
                close_data = data['close']
                print(f"  - Close prices: {len(close_data)} values")
                
                # Get latest values
                if close_data:
                    latest_idx = max(close_data.keys(), key=int)
                    latest_price = close_data[latest_idx]
                    print(f"  - Latest price: {latest_price}")
            
            if 'index' in data:
                timestamps = data['index']
                if timestamps:
                    print(f"  - Latest time: {timestamps[-1]}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error checking sample data: {e}")
            return False
    
    def test_backend_api(self):
        """Test backend API endpoints"""
        print("\n🔍 Testing Backend API...")
        
        try:
            # Test health endpoint
            response = requests.get(f"{self.backend_url}/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                print("✅ Backend health check passed")
                print(f"  - Status: {health.get('status')}")
                print(f"  - Redis connected: {health.get('components', {}).get('redis')}")
                print(f"  - MT5 connected: {health.get('components', {}).get('mt5')}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
            
        except Exception as e:
            print(f"❌ Backend health check error: {e}")
            return False
        
        try:
            # Test symbols endpoint
            response = requests.get(f"{self.backend_url}/symbols", timeout=5)
            if response.status_code == 200:
                symbols = response.json()
                print(f"✅ Symbols endpoint: {len(symbols.get('symbols', []))} symbols")
                print(f"  - Symbols: {symbols.get('symbols', [])[:5]}")
            
        except Exception as e:
            print(f"⚠️ Symbols endpoint error: {e}")
        
        try:
            # Test OHLC endpoint
            response = requests.get(f"{self.backend_url}/ohlc/EURUSD?limit=5", timeout=5)
            if response.status_code == 200:
                ohlc = response.json()
                print(f"✅ OHLC endpoint: {ohlc.get('count', 0)} bars")
                
                if ohlc.get('data'):
                    latest = ohlc['data'][-1]
                    print(f"  - Latest EURUSD: {latest.get('close')} at {latest.get('timestamp')}")
                
                return True
            else:
                print(f"❌ OHLC endpoint failed: {response.status_code}")
                return False
            
        except Exception as e:
            print(f"❌ OHLC endpoint error: {e}")
            return False
    
    def check_system_status(self):
        """Check MT5 system status in Redis"""
        print("\n🔍 Checking MT5 system status...")
        try:
            status_data = self.redis_client.get('mt5:system:status')
            
            if status_data:
                status = json.loads(status_data)
                print("✅ MT5 system status found:")
                print(f"  - MT5 connected: {status.get('mt5_connected')}")
                print(f"  - Redis connected: {status.get('redis_connected')}")
                print(f"  - Running: {status.get('running')}")
                print(f"  - Last update: {status.get('last_update')}")
                print(f"  - Symbols: {len(status.get('symbols', []))}")
                return True
            else:
                print("⚠️ No MT5 system status found")
                return False
                
        except Exception as e:
            print(f"❌ Error checking system status: {e}")
            return False
    
    def run_full_test(self):
        """Run complete test suite"""
        print("🚀 Starting MT5 Redis Integration Test")
        print("=" * 50)
        
        tests = [
            ("Redis Connection", self.test_redis_connection),
            ("Redis Keys", self.check_redis_keys),
            ("Sample Data", self.check_sample_data),
            ("System Status", self.check_system_status),
            ("Backend API", self.test_backend_api),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n{'='*20} {test_name} {'='*20}")
            try:
                if test_func():
                    passed += 1
                    print(f"✅ {test_name} PASSED")
                else:
                    print(f"❌ {test_name} FAILED")
            except Exception as e:
                print(f"❌ {test_name} ERROR: {e}")
        
        print(f"\n{'='*50}")
        print(f"🎯 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! MT5 integration is working!")
        elif passed >= 3:
            print("⚠️ Partial success - some issues detected")
        else:
            print("❌ Major issues detected - check configuration")
        
        return passed == total

def main():
    """Main function"""
    print("🧪 MT5 Redis Integration Test")
    
    tester = MT5RedisTest()
    success = tester.run_full_test()
    
    if not success:
        print("\n💡 Troubleshooting tips:")
        print("1. Ensure all containers are running: docker-compose ps")
        print("2. Check MT5 container logs: docker logs mt5-real")
        print("3. Check connector logs: docker logs mt5-connector")
        print("4. Verify MT5 is connected to broker via web interface: http://localhost:3000")
        print("5. Wait a few minutes for MT5 to fully initialize")

if __name__ == "__main__":
    main()