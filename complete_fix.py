#!/usr/bin/env python3
"""
Complete Fix - Rewrite the entire get_ohlc_data method
"""

import subprocess
import time
import requests

def show_current_backend():
    """Show the current problematic section"""
    print("📋 Current backend code around get_ohlc_data:")
    
    try:
        with open('backend_service.py', 'r') as f:
            lines = f.readlines()
        
        # Find the get_ohlc_data method
        in_method = False
        for i, line in enumerate(lines):
            if 'def get_ohlc_data(self' in line:
                in_method = True
                start_line = i
            elif in_method and line.strip().startswith('def ') and 'get_ohlc_data' not in line:
                end_line = i
                break
        else:
            end_line = len(lines)
        
        if in_method:
            print(f"📍 Method found at lines {start_line}-{end_line}")
            
            # Show the critical section
            for i in range(start_line, min(start_line + 50, end_line)):
                if 'if \'timestamp\' in df_dict:' in lines[i] or 'if \'index\' in df_dict:' in lines[i]:
                    print(f"🔍 Line {i+1}: {lines[i].strip()}")
                    for j in range(i+1, min(i+10, end_line)):
                        print(f"    {j+1}: {lines[j].rstrip()}")
                    break
        
    except Exception as e:
        print(f"❌ Error reading backend: {e}")

def create_fixed_backend():
    """Create a completely fixed backend file"""
    print("🔧 Creating fixed backend...")
    
    try:
        with open('backend_service.py', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ backend_service.py not found")
        return False
    
    # Find and replace the entire get_ohlc_data method
    start_marker = "def get_ohlc_data(self, symbol: str, timeframe: str = \"15\", limit: int = 100):"
    end_marker = "def get_ohlc_dataframe(self, symbol: str, timeframe: str = \"15\", limit: int = 100):"
    
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    
    if start_idx == -1:
        print("❌ get_ohlc_data method not found")
        return False
    
    if end_idx == -1:
        # If no next method, find the end of the class or file
        lines = content[start_idx:].split('\n')
        method_end = 0
        indent_level = None
        
        for i, line in enumerate(lines[1:], 1):  # Skip the def line
            if line.strip() == '':
                continue
            
            current_indent = len(line) - len(line.lstrip())
            
            if indent_level is None:
                indent_level = current_indent
            
            if line.strip() and current_indent <= 4:  # Back to class level
                method_end = i
                break
        
        end_idx = start_idx + sum(len(line) + 1 for line in lines[:method_end])
    
    # Create the new method
    new_method = '''def get_ohlc_data(self, symbol: str, timeframe: str = "15", limit: int = 100):
        """Get OHLC data for a symbol and timeframe - COMPLETELY FIXED VERSION"""
        try:
            if not self.redis_connected:
                raise HTTPException(status_code=503, detail="Redis not connected")
            
            key = f"mt5:ohlc:{symbol}:{timeframe}"
            
            # Get the JSON string from Redis
            data_str = self.redis_client.get(key)
            
            if not data_str:
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "data": [],
                    "count": 0,
                    "error": f"No data found for key: {key}"
                }
            
            # Parse the JSON DataFrame format
            try:
                df_dict = json.loads(data_str)
                logger.info(f"Loaded DataFrame dict with keys: {list(df_dict.keys())}")
                
                candles = []
                
                # NEW APPROACH: Handle DataFrame.to_dict() format properly
                if 'timestamp' in df_dict and 'close' in df_dict:
                    timestamp_data = df_dict['timestamp']
                    close_data = df_dict['close']
                    open_data = df_dict.get('open', {})
                    high_data = df_dict.get('high', {})
                    low_data = df_dict.get('low', {})
                    volume_data = df_dict.get('volume', {})
                    
                    logger.info(f"Processing {len(close_data)} data points")
                    
                    # Sort keys properly and create candles
                    for idx_key in sorted(close_data.keys(), key=lambda x: int(x)):
                        try:
                            candle = {
                                'timestamp': timestamp_data.get(idx_key, f"2025-06-25T{int(idx_key):02d}:00:00"),
                                'open': float(open_data.get(idx_key, 0)),
                                'high': float(high_data.get(idx_key, 0)),
                                'low': float(low_data.get(idx_key, 0)),
                                'close': float(close_data.get(idx_key, 0)),
                                'volume': int(volume_data.get(idx_key, 0))
                            }
                            
                            # Validate the candle has real data
                            if candle['close'] > 0:
                                candles.append(candle)
                            
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Skipping invalid candle at index {idx_key}: {e}")
                            continue
                    
                    logger.info(f"Created {len(candles)} valid candles")
                else:
                    logger.error(f"Missing required keys. Available: {list(df_dict.keys())}")
                
                # Apply limit (get last N candles)
                if limit > 0 and len(candles) > limit:
                    candles = candles[-limit:]
                
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "data": candles,
                    "count": len(candles),
                    "key_type": "dataframe_json_fixed_v2",
                    "total_available": len(df_dict.get('close', {}))
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                return {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "data": [],
                    "count": 0,
                    "error": f"Invalid JSON format: {str(e)}"
                }
                
        except Exception as e:
            logger.error(f"Error getting OHLC data: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    '''
    
    # Replace the method
    new_content = content[:start_idx] + new_method + content[end_idx:]
    
    # Write back
    with open('backend_service.py', 'w') as f:
        f.write(new_content)
    
    print("✅ Completely rewrote get_ohlc_data method")
    return True

def restart_and_test():
    """Restart backend and test thoroughly"""
    print("\n🔄 Restarting backend...")
    
    # Stop and start backend
    subprocess.run(['docker', 'compose', 'stop', 'trading-backend'], 
                  capture_output=True)
    subprocess.run(['docker', 'compose', 'up', '-d', 'trading-backend'], 
                  capture_output=True)
    
    print("⏱️ Waiting for backend to start...")
    time.sleep(8)
    
    print("🧪 Testing all endpoints...")
    
    test_cases = [
        ('EURUSD', '15'),
        ('GBPUSD', '15'),
        ('USDJPY', '60'),
        ('USDCAD', '1440'),
        ('AUDUSD', '15')
    ]
    
    success_count = 0
    
    for symbol, timeframe in test_cases:
        try:
            url = f'http://localhost:8009/ohlc/{symbol}?timeframe={timeframe}&limit=3'
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data['count'] > 0:
                    latest = data['data'][-1]
                    print(f"✅ {symbol:>7} {timeframe:>4}: {data['count']} bars | Latest: O:{latest['open']:.5f} C:{latest['close']:.5f}")
                    success_count += 1
                else:
                    print(f"❌ {symbol:>7} {timeframe:>4}: No data - {data.get('error', 'Unknown')}")
            else:
                print(f"❌ {symbol:>7} {timeframe:>4}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ {symbol:>7} {timeframe:>4}: {e}")
    
    return success_count

if __name__ == "__main__":
    print("🔧 Complete Backend Fix")
    print("=" * 30)
    
    show_current_backend()
    
    print("\n🛠️ Apply complete fix? (y/n)")
    choice = input().strip().lower()
    
    if choice == 'y':
        if create_fixed_backend():
            success_count = restart_and_test()
            
            if success_count > 0:
                print(f"\n🎉 SUCCESS! {success_count}/{len(['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD'])} endpoints working!")
                print("\n🔗 Try these commands:")
                print("curl -X GET 'http://localhost:8009/ohlc/EURUSD?limit=5' | jq")
                print("curl -X GET 'http://localhost:8009/symbols' | jq")
                print("curl -X GET 'http://localhost:8009/health' | jq")
            else:
                print("\n😞 Still not working. Let's check logs:")
                print("docker compose logs trading-backend | tail -20")
        else:
            print("❌ Failed to fix backend")
    else:
        print("👍 Skipped fix")