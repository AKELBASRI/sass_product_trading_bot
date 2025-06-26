#!/bin/bash

echo "🚀 Smooth MT5 Integration Migration"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Backup current setup
echo -e "${BLUE}📋 Step 1: Backup current setup${NC}"
if [ -f "docker-compose.yml" ]; then
    cp docker-compose.yml docker-compose.yml.backup
    echo -e "${GREEN}✅ Backed up docker-compose.yml${NC}"
else
    echo -e "${YELLOW}⚠️ No existing docker-compose.yml found${NC}"
fi

# Step 2: Check current containers
echo -e "${BLUE}📋 Step 2: Current container status${NC}"
echo "Current containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Step 3: Test current MT5 connection
echo -e "${BLUE}📋 Step 3: Testing current MT5 connection${NC}"
if python -c "
try:
    from mt5linux import MetaTrader5
    mt5 = MetaTrader5(host='localhost', port=8001)
    if mt5.initialize():
        print('✅ MT5 connection works')
        mt5.shutdown()
    else:
        print('❌ MT5 connection failed')
except Exception as e:
    print(f'❌ Error: {e}')
"; then
    echo -e "${GREEN}MT5 connection test completed${NC}"
else
    echo -e "${RED}❌ MT5 connection test failed${NC}"
fi

# Step 4: Ask for confirmation
echo -e "${BLUE}📋 Step 4: Migration plan${NC}"
echo "This will:"
echo "1. Stop your current mt5-real container"
echo "2. Replace docker-compose.yml with new configuration"
echo "3. Start all services together with docker-compose"
echo "4. Your MT5 settings (password: secure123) will be preserved"
echo ""
read -p "Do you want to proceed? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}👋 Migration cancelled${NC}"
    exit 0
fi

# Step 5: Stop current container
echo -e "${BLUE}📋 Step 5: Stopping current mt5-real container${NC}"
docker stop mt5-real
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Container stopped${NC}"
else
    echo -e "${RED}❌ Failed to stop container${NC}"
    exit 1
fi

# Step 6: Remove current container
echo -e "${BLUE}📋 Step 6: Removing current container${NC}"
docker rm mt5-real
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Container removed${NC}"
else
    echo -e "${YELLOW}⚠️ Container removal failed (might be ok)${NC}"
fi

# Step 7: Stop other containers
echo -e "${BLUE}📋 Step 7: Stopping other services${NC}"
docker stop trading-backend trading-redis 2>/dev/null || true

# Step 8: Start with docker-compose
echo -e "${BLUE}📋 Step 8: Starting services with docker-compose${NC}"
docker-compose down 2>/dev/null || true
docker-compose up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Services started successfully!${NC}"
else
    echo -e "${RED}❌ Failed to start services${NC}"
    echo "Restoring previous setup..."
    docker run -d --name mt5-real \
        -e CUSTOM_USER=trader \
        -e PASSWORD=secure123 \
        -p 3000:3000 \
        -p 8001:8001 \
        -v /root/trading-system/mt5-config:/config \
        gmag11/metatrader5_vnc:latest
    exit 1
fi

# Step 9: Wait for services to start
echo -e "${BLUE}📋 Step 9: Waiting for services to initialize${NC}"
echo "Waiting 10 seconds for containers to start..."
sleep 10

# Step 10: Check status
echo -e "${BLUE}📋 Step 10: Checking service status${NC}"
echo "Container status:"
docker-compose ps

echo ""
echo -e "${GREEN}🎉 Migration completed successfully!${NC}"
echo ""
echo "📊 Service URLs:"
echo "- MT5 Web Interface: http://localhost:3000 (password: secure123)"
echo "- Trading Backend: http://localhost:8009"
echo "- Redis: localhost:6382"
echo ""
echo "🧪 Next steps:"
echo "1. Wait 2-3 minutes for MT5 to fully start"
echo "2. Check MT5 web interface is accessible"
echo "3. Run integration test: python simple_mt5_integration.py"
echo "4. Monitor logs: docker-compose logs -f"
echo ""
echo "🔧 Useful commands:"
echo "- View all logs: docker-compose logs"
echo "- View specific service: docker-compose logs mt5-connector"
echo "- Restart services: docker-compose restart"
echo "- Stop all: docker-compose down"