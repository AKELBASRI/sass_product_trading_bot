#!/usr/bin/env python3
"""
Check what code is actually running in the container
"""

import subprocess
import requests
import time

def check_container_file():
    """Check what's actually in the running container"""
    print("🐳 Checking code in running container...")
    
    try:
        # Get the backend code from inside the container
        cmd = ['docker', 'exec', 'trading-backend', 'cat', '/app/backend_service.py']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            content = result.stdout
            
            # Check for our fixes
            if "if 'timestamp' in df_dict:" in content:
                print("✅ Container has 'timestamp' check")
            elif "if 'index' in df_dict:" in content:
                print("❌ Container still has OLD 'index' check!")
                return False
            
            # Find the method and show key parts
            lines = content.split('\n')
            in_method = False
            for i, line in enumerate(lines):
                if 'def get_ohlc_data(self' in line:
                    in_method = True
                    print(f"\n📋 Container method starts at line {i+1}")
                elif in_method and ('if \'timestamp\' in df_dict:' in line or 'if \'index\' in df_dict:' in line):
                    print(f"🔍 Key logic at line {i+1}: {line.strip()}")
                    # Show next few lines
                    for j in range(i+1, min(i+8, len(lines))):
                        if lines[j].strip():
                            print(f"  {j+1}: {lines[j]}")
                        if 'for idx_key in sorted(' in lines[j]:
                            break
                    break
                elif in_method and line.strip().startswith('def ') and 'get_ohlc_data' not in line:
                    break
            
            return True
            
        else:
            print(f"❌ Failed to get container file: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking container: {e}")
        return False

def force_rebuild_container():
    """Force rebuild the container with latest code"""
    print("\n🔨 Force rebuilding container...")
    
    try:
        # Stop the backend
        print("🛑 Stopping backend...")
        subprocess.run(['docker', 'compose', 'stop', 'trading-backend'], 
                      capture_output=True)
        
        # Remove the container to force rebuild
        print("🗑️ Removing old container...")
        subprocess.run(['docker', 'rm', 'trading-backend'], 
                      capture_output=True)
        
        # Remove the image to force complete rebuild
        print("🗑️ Removing old image...")
        subprocess.run(['docker', 'rmi', 'trading-system-trading-backend'], 
                      capture_output=True)
        
        # Rebuild and start
        print("🔨 Rebuilding and starting...")
        result = subprocess.run(['docker', 'compose', 'up', '-d', '--build', 'trading-backend'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Container rebuilt successfully")
            return True
        else:
            print(f"❌ Rebuild failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error rebuilding: {e}")
        return False

def test_api_with_debug():
    """Test API and show detailed response"""
    print("\n🧪 Testing API with debug...")
    
    time.sleep(5)  # Wait for startup
    
    # Test the debug endpoint first
    try:
        response = requests.get('http://localhost:8009/debug-raw/EURUSD?timeframe=15', timeout=10)
        if response.status_code == 200:
            debug_data = response.json()
            print(f"📋 Debug response: {debug_data}")
        else:
            print(f"❌ Debug endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Debug endpoint error: {e}")
    
    # Test regular endpoint
    try:
        response = requests.get('http://localhost:8009/ohlc/EURUSD?limit=3', timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 OHLC Response:")
            print(f"  - Count: {data['count']}")
            print(f"  - Data length: {len(data['data'])}")
            if data['data']:
                print(f"  - First candle: {data['data'][0]}")
                return True
            else:
                print(f"  - Error: {data.get('error', 'No error message')}")
                return False
        else:
            print(f"❌ OHLC endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ OHLC endpoint error: {e}")
        return False

def check_logs():
    """Check recent container logs"""
    print("\n📋 Recent container logs:")
    
    try:
        result = subprocess.run(['docker', 'compose', 'logs', '--tail', '10', 'trading-backend'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("❌ Failed to get logs")
    except Exception as e:
        print(f"❌ Error getting logs: {e}")

if __name__ == "__main__":
    print("🔍 Container Code Checker")
    print("=" * 30)
    
    # First check what's actually running
    container_ok = check_container_file()
    
    if not container_ok:
        print("\n❌ Container has old code. Need to rebuild.")
        print("🛠️ Rebuild container? (y/n)")
        choice = input().strip().lower()
        
        if choice == 'y':
            if force_rebuild_container():
                print("✅ Container rebuilt")
                
                # Check again
                time.sleep(3)
                if check_container_file():
                    print("✅ Container now has updated code")
                else:
                    print("❌ Container still has old code")
            else:
                print("❌ Rebuild failed")
        else:
            print("👍 Skipped rebuild")
    else:
        print("✅ Container has updated code")
    
    # Test the API
    if test_api_with_debug():
        print("\n🎉 SUCCESS! API is working!")
    else:
        print("\n😞 API still not working")
        check_logs()