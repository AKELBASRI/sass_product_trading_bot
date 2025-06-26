#!/usr/bin/env python3
"""
Quick Setup - Connect MT5 to Redis Pipeline (Fixed Version)
"""

import os
import sys
import subprocess
import time
import requests
import redis
from datetime import datetime

def check_docker():
    """Check if Docker is available"""
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True)
        return result.returncode == 0
    except:
        return False

def check_services():
    """Check if required services are running"""
    print("🔍 Checking Services...")
    
    results = {}
    
    # Check Redis
    try:
        r = redis.Redis(host='localhost', port=6382, decode_responses=True)
        r.ping()
        results['redis'] = True
        print("✅ Redis is running")
    except:
        results['redis'] = False
        print("❌ Redis is not accessible")
    
    # Check Backend
    try:
        response = requests.get('http://localhost:8009/health', timeout=5)
        results['backend'] = response.status_code == 200
        if results['backend']:
            print("✅ Trading backend is running")
        else:
            print(f"❌ Trading backend returned {response.status_code}")
    except:
        results['backend'] = False
        print("❌ Trading backend is not accessible")
    
    # Check MT5 container
    try:
        result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
        results['mt5'] = 'mt5-real' in result.stdout
        if results['mt5']:
            print("✅ MT5 container is running")
        else:
            print("❌ MT5 container is not running")
    except:
        results['mt5'] = False
        print("❌ Cannot check MT5 container")
    
    return results

def setup_files():
    """Create necessary files"""
    print("\n📁 Setting up files...")
    
    # Create directories
    os.makedirs('logs', exist_ok=True)
    print("✅ Created logs directory")
    
    # Save the connector script (without mt5linux dependency)
    connector_code = '''#!/usr/bin/env python3
"""
MT5 Data Connector - Uses host MT5 connection to populate Redis
"""

import os
import time
import json
import logging
import sys
import subprocess
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_host_script():
    """Run the data fetching script on the host"""
    host_script = """
import json
import time
import redis
import pandas as pd
from mt5linux import MetaTrader5
from datetime import datetime

# Connect to Redis (from container perspective)
r = redis.Redis(host='redis', port=6379, decode_responses=True)

# Connect to MT5
mt5 = MetaTrader5(host='mt5-real', port=8001)
if not mt5.initialize():
    print("Failed to connect to MT5")
    exit(1)

print("Connected to MT5")

# Symbols and timeframes
symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD']
timeframes = {
    '1': mt5.TIMEFRAME_M1,
    '5': mt5.TIMEFRAME_M5,
    '15': mt5.TIMEFRAME_M15,
    '30': mt5.TIMEFRAME_M30,
    '60': mt5.TIMEFRAME_H1,
    '240': mt5.TIMEFRAME_H4,
    '1440': mt5.TIMEFRAME_D1
}

success_count = 0
total_count = len(symbols) * len(timeframes)

for symbol in symbols:
    for tf_key, tf_value in timeframes.items():
        try:
            # Fetch data
            rates = mt5.copy_rates_from_pos(symbol, tf_value, 0, 1000)
            
            if rates is not None and len(rates) > 0:
                # Convert to DataFrame
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df = df.rename(columns={'time': 'timestamp', 'tick_volume': 'volume'})
                df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')
                
                # Store in Redis
                key = f"mt5:ohlc:{symbol}:{tf_key}"
                df_dict = df.to_dict()
                r.setex(key, 86400, json.dumps(df_dict, default=str))
                
                print(f"Stored {len(df)} bars for {symbol} {tf_key}")
                success_count += 1
            
            time.sleep(0.1)  # Small delay
            
        except Exception as e:
            print(f"Error processing {symbol} {tf_key}: {e}")

mt5.shutdown()
print(f"Completed: {success_count}/{total_count} successful")

# Update status
status_data = {
    'status': 'running',
    'timestamp': datetime.now().isoformat(),
    'message': f'Data updated: {success_count}/{total_count} successful',
    'symbols': symbols,
    'timeframes': list(timeframes.keys())
}
r.setex('mt5:connector:status', 300, json.dumps(status_data))
"""
    
    # Save to temp file and run on host
    with open('/tmp/mt5_fetch.py', 'w') as f:
        f.write(host_script)
    
    return host_script

class MT5DataConnector:
    def __init__(self):
        self.update_interval = int(os.getenv('UPDATE_INTERVAL', 300))  # 5 minutes
        self.running = False
    
    def run(self):
        """Main loop - periodically trigger host script"""
        logger.info("🚀 Starting MT5 Data Connector (Host Mode)")
        self.running = True
        
        host_script = run_host_script()
        
        try:
            while self.running:
                logger.info("🔄 Triggering data fetch on host...")
                
                try:
                    # Execute the script on the host via docker exec
                    cmd = [
                        'docker', 'exec', '-i', 'mt5-real',
                        'python3', '-c', host_script
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    
                    if result.returncode == 0:
                        logger.info("✅ Data fetch completed successfully")
                        logger.info(result.stdout)
                    else:
                        logger.error(f"❌ Data fetch failed: {result.stderr}")
                
                except subprocess.TimeoutExpired:
                    logger.error("❌ Data fetch timed out")
                except Exception as e:
                    logger.error(f"❌ Error executing data fetch: {e}")
                
                logger.info(f"💤 Sleeping for {self.update_interval} seconds...")
                time.sleep(self.update_interval)
                
        except KeyboardInterrupt:
            logger.info("🛑 Received stop signal")
        finally:
            self.running = False
            logger.info("🛑 MT5 Data Connector stopped")

if __name__ == "__main__":
    connector = MT5DataConnector()
    connector.run()
'''
    
    with open('mt5_data_connector.py', 'w') as f:
        f.write(connector_code)
    print("✅ Created mt5_data_connector.py (host-based)")
    
    # Create simplified Dockerfile
    dockerfile_content = '''FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \\
    redis \\
    requests

# Create logs directory
RUN mkdir -p /app/logs

# Copy the connector script
COPY mt5_data_connector.py /app/

# Make sure the script is executable
RUN chmod +x /app/mt5_data_connector.py

# Run the connector
CMD ["python", "/app/mt5_data_connector.py"]
'''
    
    with open('Dockerfile.mt5-connector', 'w') as f:
        f.write(dockerfile_content)
    print("✅ Created Dockerfile.mt5-connector (simplified)")

def run_simple_test():
    """Run a simple data connector test without Docker"""
    print("\n🧪 Running Simple Test...")
    
    try:
        # Import required modules
        from mt5linux import MetaTrader5
        import redis
        import pandas as pd
        import json
        
        # Connect to Redis
        r = redis.Redis(host='localhost', port=6382, decode_responses=True)
        r.ping()
        print("✅ Connected to Redis")
        
        # Connect to MT5
        mt5 = MetaTrader5(host='localhost', port=8001)
        if not mt5.initialize():
            print("❌ Failed to connect to MT5")
            return False
        
        print("✅ Connected to MT5")
        
        # Test symbols and timeframes
        symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD']
        timeframes = {
            '15': MetaTrader5.TIMEFRAME_M15,
            '60': MetaTrader5.TIMEFRAME_H1,
            '1440': MetaTrader5.TIMEFRAME_D1
        }
        
        success_count = 0
        total_count = len(symbols) * len(timeframes)
        
        print(f"📊 Fetching data for {len(symbols)} symbols, {len(timeframes)} timeframes...")
        
        for symbol in symbols:
            for tf_key, tf_value in timeframes.items():
                try:
                    # Fetch data
                    rates = mt5.copy_rates_from_pos(symbol, tf_value, 0, 500)
                    
                    if rates is not None and len(rates) > 0:
                        # Convert to DataFrame
                        df = pd.DataFrame(rates)
                        df['time'] = pd.to_datetime(df['time'], unit='s')
                        df = df.rename(columns={'time': 'timestamp', 'tick_volume': 'volume'})
                        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
                        df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')
                        
                        # Store in Redis
                        key = f"mt5:ohlc:{symbol}:{tf_key}"
                        df_dict = df.to_dict()
                        r.setex(key, 3600, json.dumps(df_dict, default=str))  # 1 hour expiry
                        
                        print(f"✅ Stored {len(df)} bars for {symbol} {tf_key}")
                        success_count += 1
                    else:
                        print(f"⚠️ No data for {symbol} {tf_key}")
                
                except Exception as e:
                    print(f"❌ Error with {symbol} {tf_key}: {e}")
        
        mt5.shutdown()
        
        print(f"\n📈 Results: {success_count}/{total_count} successful")
        
        # Test the API
        print("\n🔍 Testing API...")
        time.sleep(2)
        
        test_calls = [
            ('EURUSD', '15'),
            ('GBPUSD', '15'), 
            ('USDJPY', '60')
        ]
        
        for symbol, tf in test_calls:
            try:
                response = requests.get(f'http://localhost:8009/ohlc/{symbol}?timeframe={tf}&limit=5', timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data['count'] > 0:
                        print(f"✅ {symbol} {tf}: Got {data['count']} bars, latest: {data['data'][-1]['close']}")
                    else:
                        print(f"⚠️ {symbol} {tf}: No data returned")
                else:
                    print(f"❌ {symbol} {tf}: HTTP {response.status_code}")
            except Exception as e:
                print(f"❌ {symbol} {tf}: {e}")
        
        return success_count > 0
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install mt5linux redis pandas")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def update_docker_compose():
    """Update docker-compose.yml with fixed connector service"""
    print("\n📝 Updating docker-compose.yml...")
    
    compose_content = '''services:
  # Your existing MT5 container configuration
  mt5-real:
    image: gmag11/metatrader5_vnc:latest
    container_name: mt5-real
    ports:
      - "3000:3000"  # Web VNC access
      - "8001:8001"  # Python API access
    environment:
      - CUSTOM_USER=trader
      - PASSWORD=secure123
    volumes:
      - ./mt5-config:/config
    restart: unless-stopped
    networks:
      - trading-network

  # Redis Database
  redis:
    image: redis:7-alpine
    container_name: trading-redis
    ports:
      - "6382:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - trading-network
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  # MT5 Data Connector (Fixed)
  mt5-connector:
    build:
      context: .
      dockerfile: Dockerfile.mt5-connector
    container_name: mt5-connector
    environment:
      - PYTHONUNBUFFERED=1
      - UPDATE_INTERVAL=300  # Fetch data every 5 minutes
    depends_on:
      redis:
        condition: service_healthy
      mt5-real:
        condition: service_started
    volumes:
      - ./logs:/app/logs
      - /var/run/docker.sock:/var/run/docker.sock  # Access to Docker
    restart: unless-stopped
    networks:
      - trading-network

  # Your Trading Backend
  trading-backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: trading-backend
    environment:
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - FLASK_ENV=development
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./trading_system:/app/trading_system
      - ./logs:/app/logs
    ports:
      - "8009:8009"
    restart: unless-stopped
    networks:
      - trading-network

volumes:
  redis_data:
    driver: local

networks:
  trading-network:
    driver: bridge
'''
    
    with open('docker-compose.yml', 'w') as f:
        f.write(compose_content)
    print("✅ Updated docker-compose.yml")

def main():
    print("🚀 MT5 Data Pipeline Setup (Fixed)")
    print("=" * 40)
    
    # Check prerequisites
    services = check_services()
    
    if not all([services['redis'], services['backend'], services['mt5']]):
        print("\n❌ Some required services are not running.")
        print("Please start them first with: docker compose up -d")
        return
    
    # Setup files
    setup_files()
    
    print("\n" + "=" * 40)
    print("🎯 Choose an option:")
    print("1. Run simple test (populate Redis with data)")
    print("2. Update docker-compose.yml and rebuild services")
    print("3. Check Redis data")
    print("4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == "1":
        print("\n🧪 Running simple test...")
        if run_simple_test():
            print("\n✅ Test completed successfully!")
            print("\n🔗 Try these API calls:")
            print("curl -X GET 'http://localhost:8009/ohlc/EURUSD?limit=5' | jq")
            print("curl -X GET 'http://localhost:8009/ohlc/GBPUSD?timeframe=60&limit=5' | jq")
            print("curl -X GET 'http://localhost:8009/symbols' | jq")
        else:
            print("\n❌ Test failed")
    
    elif choice == "2":
        print("\n🔨 Updating docker-compose and rebuilding...")
        
        # Update compose file
        update_docker_compose()
        
        if check_docker():
            # Stop existing services
            print("🛑 Stopping existing services...")
            subprocess.run(['docker', 'compose', 'down'], cwd='.')
            
            # Rebuild and start
            print("🔨 Building and starting services...")
            result = subprocess.run(['docker', 'compose', 'up', '-d', '--build'], cwd='.')
            
            if result.returncode == 0:
                print("✅ Services started successfully")
                print("📋 Check logs with: docker compose logs -f mt5-connector")
                print("🔍 Check status with: docker compose ps")
            else:
                print("❌ Failed to start services")
        else:
            print("❌ Docker not available")
    
    elif choice == "3":
        print("\n🔍 Checking Redis data...")
        try:
            r = redis.Redis(host='localhost', port=6382, decode_responses=True)
            all_keys = r.keys("*")
            ohlc_keys = [k for k in all_keys if k.startswith("mt5:ohlc:")]
            
            print(f"📊 Total Redis keys: {len(all_keys)}")
            print(f"📈 OHLC data keys: {len(ohlc_keys)}")
            
            if ohlc_keys:
                print("\n📋 Available OHLC data:")
                for key in sorted(ohlc_keys)[:10]:  # Show first 10
                    print(f"  - {key}")
                if len(ohlc_keys) > 10:
                    print(f"  ... and {len(ohlc_keys) - 10} more")
            else:
                print("⚠️ No OHLC data found in Redis")
                
        except Exception as e:
            print(f"❌ Error checking Redis: {e}")
    
    else:
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()