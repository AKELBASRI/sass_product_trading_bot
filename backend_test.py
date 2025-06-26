import requests
import json
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List
import time

class BackendTester:
    def __init__(self, base_url: str = "http://localhost:8009"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_connection(self) -> bool:
        """Test if backend is reachable"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            print(f"✅ Backend is reachable. Status: {response.status_code}")
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"❌ Backend connection failed: {e}")
            return False
    
    def test_health_endpoint(self) -> Dict[str, Any]:
        """Test health endpoint and return detailed status"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            data = response.json()
            
            print("\n📊 HEALTH CHECK:")
            print(f"Status: {data.get('status', 'unknown')}")
            print(f"Redis Connected: {data.get('components', {}).get('redis', False)}")
            print(f"MT5 Connected: {data.get('components', {}).get('mt5', False)}")
            print(f"System Running: {data.get('components', {}).get('system', False)}")
            
            if 'details' in data:
                details = data['details']
                if 'mt5' in details:
                    ohlc_keys = details['mt5'].get('ohlc_keys', [])
                    print(f"OHLC Keys Found: {len(ohlc_keys)}")
                    if ohlc_keys:
                        print(f"Sample keys: {ohlc_keys[:3]}")
            
            return data
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return {}
    
    def test_symbols_endpoint(self) -> List[str]:
        """Test symbols endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/symbols")
            data = response.json()
            
            symbols = data.get('symbols', [])
            print(f"\n📈 AVAILABLE SYMBOLS:")
            print(f"Count: {data.get('count', 0)}")
            print(f"Symbols: {symbols}")
            
            return symbols
        except Exception as e:
            print(f"❌ Symbols test failed: {e}")
            return []
    
    def test_redis_keys(self) -> Dict[str, Any]:
        """Test Redis keys endpoint for debugging"""
        try:
            response = self.session.get(f"{self.base_url}/redis-keys")
            data = response.json()
            
            print(f"\n🔑 REDIS KEYS DEBUG:")
            print(f"Total Keys: {data.get('total_keys', 0)}")
            print(f"MT5 Keys: {len(data.get('mt5_keys', []))}")
            print(f"OHLC Keys: {len(data.get('ohlc_keys', []))}")
            
            if data.get('ohlc_keys'):
                print(f"OHLC Keys: {data['ohlc_keys'][:5]}")
            
            return data
        except Exception as e:
            print(f"❌ Redis keys test failed: {e}")
            return {}
    
    def test_ohlc_endpoint(self, symbol: str, timeframe: str = "15", limit: int = 10) -> Dict[str, Any]:
        """Test OHLC data endpoint for a specific symbol"""
        try:
            url = f"{self.base_url}/ohlc/{symbol}"
            params = {"timeframe": timeframe, "limit": limit}
            
            response = self.session.get(url, params=params)
            data = response.json()
            
            print(f"\n📊 OHLC DATA TEST for {symbol}:")
            print(f"Symbol: {data.get('symbol', 'N/A')}")
            print(f"Timeframe: {data.get('timeframe', 'N/A')}")
            print(f"Data Count: {data.get('count', 0)}")
            print(f"Total Available: {data.get('total_available', 'N/A')}")
            
            if data.get('error'):
                print(f"❌ Error: {data['error']}")
            elif data.get('data'):
                candles = data['data']
                if candles:
                    latest = candles[-1]
                    print(f"Latest Candle:")
                    print(f"  Timestamp: {latest.get('timestamp', 'N/A')}")
                    print(f"  OHLC: {latest.get('open', 0):.5f} / {latest.get('high', 0):.5f} / {latest.get('low', 0):.5f} / {latest.get('close', 0):.5f}")
                    print(f"  Volume: {latest.get('volume', 0)}")
                    
                    # Validate data structure
                    required_fields = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                    missing_fields = [field for field in required_fields if field not in latest]
                    if missing_fields:
                        print(f"⚠️  Missing fields: {missing_fields}")
                    else:
                        print("✅ All required fields present")
            
            return data
        except Exception as e:
            print(f"❌ OHLC test failed for {symbol}: {e}")
            return {}
    
    def test_ohlc_dataframe_endpoint(self, symbol: str, timeframe: str = "15", limit: int = 10) -> Dict[str, Any]:
        """Test OHLC DataFrame endpoint"""
        try:
            url = f"{self.base_url}/ohlc/{symbol}/dataframe"
            params = {"timeframe": timeframe, "limit": limit}
            
            response = self.session.get(url, params=params)
            data = response.json()
            
            print(f"\n📈 OHLC DATAFRAME TEST for {symbol}:")
            
            if data.get('error'):
                print(f"❌ Error: {data['error']}")
            else:
                print(f"Symbol: {data.get('symbol', 'N/A')}")
                print(f"Timeframe: {data.get('timeframe', 'N/A')}")
                print(f"Shape: {data.get('shape', 'N/A')}")
                print(f"Columns: {data.get('columns', [])}")
                
                stats = data.get('stats', {})
                if stats:
                    print(f"Stats:")
                    print(f"  Count: {stats.get('count', 0)}")
                    print(f"  Latest Price: {stats.get('latest_price', 'N/A')}")
                    print(f"  Price Change: {stats.get('price_change', 'N/A')}")
                    print(f"  24h High: {stats.get('high_24h', 'N/A')}")
                    print(f"  24h Low: {stats.get('low_24h', 'N/A')}")
            
            return data
        except Exception as e:
            print(f"❌ DataFrame test failed for {symbol}: {e}")
            return {}
    
    def test_debug_raw_data(self, symbol: str, timeframe: str = "15") -> Dict[str, Any]:
        """Test debug raw data endpoint"""
        try:
            url = f"{self.base_url}/debug-raw/{symbol}"
            params = {"timeframe": timeframe}
            
            response = self.session.get(url, params=params)
            data = response.json()
            
            print(f"\n🔍 RAW DATA DEBUG for {symbol}:")
            print(f"Key: {data.get('key', 'N/A')}")
            print(f"Data Type: {data.get('data_type', 'N/A')}")
            print(f"Keys: {data.get('keys', 'N/A')}")
            print(f"Data Length: {data.get('data_length', 'N/A')}")
            
            if data.get('sample'):
                print(f"Sample: {data['sample']}")
            
            return data
        except Exception as e:
            print(f"❌ Raw data debug failed for {symbol}: {e}")
            return {}
    
    def run_comprehensive_test(self):
        """Run all tests in sequence"""
        print("🚀 Starting Comprehensive Backend Test")
        print("=" * 50)
        
        # Test connection
        if not self.test_connection():
            print("❌ Cannot proceed - backend not reachable")
            return
        
        # Test health
        health_data = self.test_health_endpoint()
        
        # Test Redis keys
        redis_data = self.test_redis_keys()
        
        # Test symbols
        symbols = self.test_symbols_endpoint()
        
        # Test OHLC data for available symbols
        if symbols:
            # Test first available symbol
            test_symbol = symbols[0]
            print(f"\n🎯 Testing with symbol: {test_symbol}")
            
            # Test debug raw data first
            self.test_debug_raw_data(test_symbol)
            
            # Test OHLC endpoint
            ohlc_data = self.test_ohlc_endpoint(test_symbol)
            
            # Test DataFrame endpoint
            df_data = self.test_ohlc_dataframe_endpoint(test_symbol)
            
            # Test multiple timeframes
            timeframes = ["15", "30", "60"]
            for tf in timeframes:
                print(f"\n📊 Testing timeframe {tf}m:")
                self.test_ohlc_endpoint(test_symbol, tf, 5)
        else:
            print("⚠️  No symbols available to test")
        
        print("\n" + "=" * 50)
        print("✅ Comprehensive test completed!")

def validate_ohlc_data_for_frontend(data: Dict[str, Any]) -> bool:
    """Validate if OHLC data is suitable for lightweight-charts"""
    try:
        if not data.get('data'):
            print("❌ No data array found")
            return False
        
        candles = data['data']
        if not candles:
            print("❌ Empty data array")
            return False
        
        # Check first candle structure
        first_candle = candles[0]
        required_fields = ['timestamp', 'open', 'high', 'low', 'close']
        
        for field in required_fields:
            if field not in first_candle:
                print(f"❌ Missing required field: {field}")
                return False
        
        # Validate data types
        try:
            float(first_candle['open'])
            float(first_candle['high'])
            float(first_candle['low'])
            float(first_candle['close'])
        except (ValueError, TypeError):
            print("❌ Invalid numeric data in OHLC fields")
            return False
        
        # Check timestamp format
        timestamp = first_candle['timestamp']
        if not isinstance(timestamp, str):
            print("❌ Timestamp should be string")
            return False
        
        print("✅ OHLC data is valid for lightweight-charts")
        print(f"✅ Found {len(candles)} candles")
        print(f"✅ Price range: {min(c['low'] for c in candles):.5f} - {max(c['high'] for c in candles):.5f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Validation error: {e}")
        return False

if __name__ == "__main__":
    # Test with your backend URL
    tester = BackendTester("http://localhost:8009")
    
    print("Testing Backend OHLC Data Endpoints")
    print("===================================")
    
    # Run comprehensive test
    tester.run_comprehensive_test()
    
    # Additional validation for frontend integration
    print("\n🎨 FRONTEND INTEGRATION VALIDATION:")
    symbols = tester.test_symbols_endpoint()
    if symbols:
        ohlc_data = tester.test_ohlc_endpoint(symbols[0], "15", 50)
        if ohlc_data:
            validate_ohlc_data_for_frontend(ohlc_data)
