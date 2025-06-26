#!/bin/bash
# migrate_to_wine_mt5.sh
# Script to migrate from mt5linux to Wine-based MT5

echo "=== MT5 Wine Migration Script ==="
echo "This script will help you migrate to the Wine-based MT5 solution"
echo ""

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running. Please start Docker first."
    exit 1
fi

# Function to check service health
check_service_health() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=0
    
    echo -n "Checking $service health"
    while [ $attempt -lt $max_attempts ]; do
        if nc -z localhost $port 2>/dev/null; then
            echo " ?"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    echo " ?"
    return 1
}

# Step 1: Create backup of current setup
echo ""
echo "Step 1: Creating backup of current configuration..."
mkdir -p backups/$(date +%Y%m%d_%H%M%S)
cp docker-compose.yml backups/$(date +%Y%m%d_%H%M%S)/
cp Dockerfile.mt5 backups/$(date +%Y%m%d_%H%M%S)/
cp mt5_connector_enhanced.py backups/$(date +%Y%m%d_%H%M%S)/
echo "Backup created in backups/$(date +%Y%m%d_%H%M%S)/"

# Step 2: Stop current services if running
echo ""
echo "Step 2: Stopping current services..."
docker compose down

# Step 3: Create new files
echo ""
echo "Step 3: Creating new Wine-based configuration files..."
echo "Please ensure you have created:"
echo "  - Dockerfile.mt5.wine"
echo "  - mt5_connector_wine_adapter.py"
echo "  - docker-entrypoint-mt5-wine.sh"
echo "  - docker-compose.integrated.yml"
echo ""
read -p "Have you created these files? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please create the files first, then run this script again."
    exit 1
fi

# Step 4: Make scripts executable
chmod +x docker-entrypoint-mt5-wine.sh

# Step 5: Build new Wine-based image
echo ""
echo "Step 4: Building Wine-based MT5 image..."
docker build -t mt5-wine -f Dockerfile.mt5.wine .

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to build Wine-based MT5 image"
    exit 1
fi

# Step 6: Start services with new configuration
echo ""
echo "Step 5: Starting services with Wine-based MT5..."
docker compose -f docker-compose.integrated.yml up -d

# Step 7: Wait for services to be ready
echo ""
echo "Step 6: Waiting for services to initialize..."
sleep 10

# Check Redis
check_service_health "Redis" 6381
if [ $? -ne 0 ]; then
    echo "ERROR: Redis failed to start"
    docker compose -f docker-compose.integrated.yml logs redis
    exit 1
fi

# Check Wine MT5 VNC
check_service_health "MT5 Wine VNC" 3000
if [ $? -ne 0 ]; then
    echo "WARNING: VNC interface not accessible"
fi

# Check RPyC
echo "Waiting for MT5 to fully initialize (this may take 2-3 minutes)..."
sleep 60
check_service_health "MT5 RPyC" 8001
if [ $? -ne 0 ]; then
    echo "ERROR: RPyC server failed to start"
    docker compose -f docker-compose.integrated.yml logs mt5-wine
    exit 1
fi

# Check Backend
check_service_health "Trading Backend" 8000
if [ $? -ne 0 ]; then
    echo "ERROR: Trading backend failed to start"
    docker compose -f docker-compose.integrated.yml logs trading-backend
    exit 1
fi

# Check Dashboard
check_service_health "Trading Dashboard" 8501
if [ $? -ne 0 ]; then
    echo "ERROR: Trading dashboard failed to start"
    docker compose -f docker-compose.integrated.yml logs trading-dashboard
    exit 1
fi

# Step 8: Test Wine MT5 connection
echo ""
echo "Step 7: Testing Wine MT5 connection..."
cat > test_wine_mt5.py << 'EOF'
import redis
import json
import time

r = redis.Redis(host='localhost', port=6381, decode_responses=True)

print("Checking MT5 Wine connection status...")
time.sleep(5)

status = r.hgetall('mt5:status')
if status and status.get('connected') == 'true':
    print("? MT5 Wine connected successfully!")
    print(f"  Account: {status.get('account')}")
    print(f"  Server: {status.get('server')}")
    print(f"  Balance: {status.get('balance')}")
    print(f"  Connection Type: {status.get('connection_type')}")
else:
    print("? MT5 Wine not connected yet")
    exit(1)

# Check for data
tick = r.hgetall('mt5:tick:EURUSD')
if tick:
    print("\n? Receiving market data:")
    print(f"  EURUSD Bid: {tick.get('bid')}")
    print(f"  EURUSD Ask: {tick.get('ask')}")
else:
    print("\n? No market data yet (market may be closed)")
EOF

python3 test_wine_mt5.py
TEST_RESULT=$?

# Step 9: Provide status and next steps
echo ""
echo "=== Migration Status ==="
if [ $TEST_RESULT -eq 0 ]; then
    echo "? Migration successful!"
    echo ""
    echo "Wine-based MT5 is now running. You can:"
    echo "1. Access MT5 interface at: http://localhost:3000"
    echo "   Username: trader"
    echo "   Password: SecurePass123"
    echo "2. Access trading dashboard at: http://localhost:8501"
    echo "3. Access trading API at: http://localhost:8000"
    echo ""
    echo "To run both old and new versions for comparison:"
    echo "  docker compose -f docker compose.integrated.yml --profile with-legacy up -d"
    echo ""
    echo "To switch back to the old version:"
    echo "  docker compose down"
    echo "  docker compose up -d"
else
    echo "? Migration completed with warnings"
    echo ""
    echo "The services are running but MT5 connection needs attention."
    echo "Please check the logs:"
    echo "  docker compose -f docker-compose.integrated.yml logs mt5-wine"
fi

echo ""
echo "Logs are available in ./logs/"
echo "Wine MT5 config is stored in ./config/"

# Cleanup
rm -f test_wine_mt5.py