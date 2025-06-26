#!/usr/bin/env python3
"""
Patch Backend - Fix the get_ohlc_data method
"""

def patch_backend_file():
    """Patch the backend service file"""
    
    # Read the current backend file
    try:
        with open('backend_service.py', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ backend_service.py not found. Looking for alternative files...")
        
        # Try to find the backend file
        import os
        for file in os.listdir('.'):
            if file.endswith('.py') and 'backend' in file.lower():
                print(f"Found: {file}")
                with open(file, 'r') as f:
                    content = f.read()
                backend_file = file
                break
        else:
            print("❌ No backend file found")
            return False
    else:
        backend_file = 'backend_service.py'
    
    print(f"📝 Patching {backend_file}...")
    
    # Find the problematic line and replace it
    old_pattern = """if 'index' in df_dict:
                    # index is already a list, not a dict
                    indices = df_dict['index']"""
    
    new_pattern = """if 'timestamp' in df_dict:
                    # Use timestamp data directly
                    timestamp_data = df_dict['timestamp']"""
    
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        print("✅ Fixed 'index' -> 'timestamp' issue")
    
    # Also fix the timestamp extraction
    old_timestamp = """'timestamp': indices[int(idx_key)] if int(idx_key) < len(indices) else f"2025-06-25T{int(idx_key):02d}:00:00","""
    new_timestamp = """'timestamp': timestamp_data.get(idx_key, f"2025-06-25T{int(idx_key):02d}:00:00"),"""
    
    if old_timestamp in content:
        content = content.replace(old_timestamp, new_timestamp)
        print("✅ Fixed timestamp extraction")
    
    # Also fix the loop iteration
    old_loop = """for idx_key in sorted(close_data.keys(), key=int):"""
    new_loop = """for idx_key in sorted(timestamp_data.keys(), key=int):"""
    
    if old_loop in content:
        content = content.replace(old_loop, new_loop)
        print("✅ Fixed loop iteration")
    
    # Write the patched content back
    with open(backend_file, 'w') as f:
        f.write(content)
    
    print(f"✅ Patched {backend_file}")
    return True

def restart_backend_container():
    """Restart the backend container with the fixed code"""
    import subprocess
    
    print("🔄 Restarting backend container...")
    
    try:
        # Stop the backend container
        result = subprocess.run(['docker', 'compose', 'stop', 'trading-backend'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Stopped backend container")
        else:
            print(f"⚠️ Stop result: {result.stderr}")
        
        # Start it again
        result = subprocess.run(['docker', 'compose', 'up', '-d', 'trading-backend'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Started backend container")
            return True
        else:
            print(f"❌ Start failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error restarting container: {e}")
        return False

def test_fix():
    """Test if the fix worked"""
    import requests
    import time
    
    print("⏱️ Waiting for backend to start...")
    time.sleep(5)
    
    print("🧪 Testing the fix...")
    
    test_cases = [
        ('EURUSD', '15'),
        ('GBPUSD', '15'),
        ('USDJPY', '60')
    ]
    
    success_count = 0
    
    for symbol, timeframe in test_cases:
        try:
            url = f'http://localhost:8009/ohlc/{symbol}?timeframe={timeframe}&limit=3'
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['count'] > 0:
                    print(f"✅ {symbol} {timeframe}: {data['count']} bars, latest price: {data['data'][-1]['close']}")
                    success_count += 1
                else:
                    print(f"❌ {symbol} {timeframe}: No data")
                    print(f"   Response: {data}")
            else:
                print(f"❌ {symbol} {timeframe}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ {symbol} {timeframe}: {e}")
    
    return success_count

if __name__ == "__main__":
    print("🔧 Backend Patch Tool")
    print("=" * 30)
    
    # Patch the backend file
    if patch_backend_file():
        print("\n🐳 Restarting backend container...")
        
        if restart_backend_container():
            print("\n🧪 Testing the fix...")
            success_count = test_fix()
            
            if success_count > 0:
                print(f"\n🎉 SUCCESS! {success_count}/3 endpoints working")
                print("\n🔗 Try these commands:")
                print("curl -X GET 'http://localhost:8009/ohlc/EURUSD?limit=5' | jq")
                print("curl -X GET 'http://localhost:8009/ohlc/GBPUSD?timeframe=60&limit=5' | jq")
                print("curl -X GET 'http://localhost:8009/symbols' | jq")
            else:
                print("\n😞 Still not working. Check the logs:")
                print("docker compose logs trading-backend")
        else:
            print("\n❌ Failed to restart container")
    else:
        print("\n❌ Failed to patch backend file")