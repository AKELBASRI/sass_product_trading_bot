import json
import sys

def test_backend():
    try:
        import requests
    except ImportError:
        print("Installing requests...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests
    
    base_url = "http://localhost:8009"
    
    print("Testing Backend OHLC Data Endpoints")
    print("===================================")
    
    # Test health
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"Health endpoint: {response.status_code}")
        health_data = response.json()
        print(f"Status: {health_data.get('status', 'unknown')}")
        print(f"Redis: {health_data.get('components', {}).get('redis', False)}")
        print(f"MT5: {health_data.get('components', {}).get('mt5', False)}")
    except Exception as e:
        print(f"Health test failed: {e}")
        return
    
    # Test symbols
    try:
        response = requests.get(f"{base_url}/symbols")
        data = response.json()
        symbols = data.get('symbols', [])
        print(f"\nAvailable symbols ({len(symbols)}): {symbols}")
        
        if symbols:
            # Test OHLC for first symbol
            symbol = symbols[0]
            response = requests.get(f"{base_url}/ohlc/{symbol}?timeframe=15&limit=10")
            ohlc_data = response.json()
            print(f"\nOHLC data for {symbol}:")
            print(f"Count: {ohlc_data.get('count', 0)}")
            
            if ohlc_data.get('data'):
                latest = ohlc_data['data'][-1]
                print(f"Latest candle:")
                print(f"  Time: {latest.get('timestamp', 'N/A')}")
                print(f"  Open: {latest.get('open', 0):.5f}")
                print(f"  High: {latest.get('high', 0):.5f}")
                print(f"  Low: {latest.get('low', 0):.5f}")
                print(f"  Close: {latest.get('close', 0):.5f}")
                print(f"  Volume: {latest.get('volume', 0)}")
                
                # Check if data is valid for charts
                required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                missing = [f for f in required if f not in latest]
                if missing:
                    print(f"Missing fields: {missing}")
                else:
                    print("Data structure is valid for charts!")
            else:
                print("No OHLC data found")
        else:
            print("No symbols available")
        
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_backend()
