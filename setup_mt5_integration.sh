#!/bin/bash

echo "🚀 Setting up MT5 Integration"
echo "=============================="

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p mt5-config
mkdir -p logs

# Set permissions
chmod 755 mt5-config
chmod 755 logs

echo "✅ Directories created"

# Install Python dependencies in your mt5_env
echo "📦 Installing Python dependencies..."
echo "Please run these commands in your mt5_env:"
echo ""
echo "  pip install redis pandas numpy rpyc mt5linux"
echo ""

# Build and start containers
echo "🐳 Building and starting containers..."
docker-compose down
docker-compose build
docker-compose up -d

echo "⏳ Waiting for containers to start..."
sleep 10

# Show container status
echo "📊 Container status:"
docker-compose ps

echo ""
echo "🌐 Web interfaces:"
echo "  - MT5 VNC: http://localhost:3000"
echo "  - Trading Backend: http://localhost:8009"
echo ""

echo "⏰ Waiting for MT5 to initialize (this takes 5-10 minutes)..."
echo "You can monitor progress with:"
echo "  docker logs -f mt5-real"
echo "  docker logs -f mt5-connector"
echo ""

echo "🧪 To test the integration:"
echo "  python test_redis_mt5.py"
echo ""

echo "✅ Setup complete! Check the web interface and run the test script."