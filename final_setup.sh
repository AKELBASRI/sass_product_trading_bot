#!/bin/bash
# setup_docker_dashboard.sh
# Setup script for Docker-based trading dashboard

echo "🚀 Setting up Docker Trading Dashboard"
echo "======================================"

# Create directory structure
echo "📁 Creating directory structure..."
mkdir -p dashboard
mkdir -p logs

# 1. Create the updated docker-compose.yml
echo "📝 Creating docker-compose.yml..."
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
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

  # Real-Time WebSocket Streamer & Dashboard
  websocket-streamer:
    build:
      context: .
      dockerfile: Dockerfile.websocket-streamer
    container_name: websocket-streamer
    environment:
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - MT5_HOST=mt5-real
      - MT5_PORT=8001
    depends_on:
      redis:
        condition: service_healthy
      mt5-real:
        condition: service_started
    volumes:
      - ./dashboard:/app/dashboard
      - ./logs:/app/logs
    ports:
      - "8010:8010"  # WebSocket & Dashboard port
    restart: unless-stopped
    networks:
      - trading-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8010/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Stream Data Creator (Optional - for continuous data)
  stream-creator:
    build:
      context: .
      dockerfile: Dockerfile.stream-creator
    container_name: stream-creator
    environment:
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - MT5_HOST=mt5-real
      - MT5_PORT=8001
      - RUN_MODE=continuous  # or 'once' for single run
    depends_on:
      redis:
        condition: service_healthy
      mt5-real:
        condition: service_started
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    networks:
      - trading-network
    profiles:
      - stream-creator  # Optional service

volumes:
  redis_data:
    driver: local

networks:
  trading-network:
    driver: bridge
EOF

# 2. Create Dockerfile for WebSocket Streamer
echo "🐳 Creating Dockerfile.websocket-streamer..."
cat > Dockerfile.websocket-streamer << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements-websocket.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-websocket.txt

# Copy application files
COPY websocket_streamer.py .
COPY dashboard/ ./dashboard/

# Create logs directory
RUN mkdir -p /app/logs

# Expose port
EXPOSE 8010

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

# Run the application
CMD ["python", "websocket_streamer.py"]
EOF

# 3. Create Dockerfile for Stream Creator
echo "🐳 Creating Dockerfile.stream-creator..."
cat > Dockerfile.stream-creator << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements-stream.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-stream.txt

# Copy application files
COPY stream_creator_docker.py .

# Create logs directory
RUN mkdir -p /app/logs

# Run the application
CMD ["python", "stream_creator_docker.py"]
EOF

# 4. Create requirements files
echo "📦 Creating requirements files..."
cat > requirements-websocket.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0
redis==5.0.1

python-multipart==0.0.6
EOF

cat > requirements-stream.txt << 'EOF'
redis==5.0.1

EOF

# 5. Create a simple dashboard HTML
echo "🎨 Creating dashboard/index.html..."
cat > dashboard/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-Time Trading Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5rem;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .controls {
            text-align: center;
            margin-bottom: 30px;
        }
        .btn {
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 12px 24px;
            margin: 0 10px;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .btn:hover {
            background: rgba(255,255,255,0.3);
            transform: translateY(-2px);
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .symbol-card {
            background: rgba(255,255,255,0.15);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(15px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .symbol-name {
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 15px;
            text-align: center;
        }
        .price-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
        }
        .price-item {
            text-align: center;
            padding: 10px;
            background: rgba(255,255,255,0.1);
            border-radius: 8px;
        }
        .price-value {
            font-size: 1.1rem;
            font-weight: bold;
            font-family: monospace;
        }
        .bid { color: #ff6b6b; }
        .ask { color: #51cf66; }
        .spread { color: #ffd43b; }
        #status {
            text-align: center;
            margin: 20px 0;
            padding: 15px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Real-Time Trading Dashboard</h1>
        <p>Docker-powered MT5 streaming system</p>
    </div>

    <div class="controls">
        <button class="btn" onclick="startStream()">🚀 Start Stream</button>
        <button class="btn" onclick="refreshData()">🔄 Refresh</button>
        <button class="btn" onclick="checkHealth()">💊 Health Check</button>
    </div>

    <div id="status">Loading...</div>

    <div class="dashboard" id="dashboard">
        <div style="text-align: center; grid-column: 1/-1; padding: 40px;">
            <div style="font-size: 1.2em;">Connecting to WebSocket...</div>
        </div>
    </div>

    <script>
        const symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD'];
        let ws = null;

        function connect() {
            const wsUrl = `ws://${window.location.hostname}:8010/ws`;
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                document.getElementById('status').innerHTML = '🟢 Connected to WebSocket';
                subscribeToSymbols();
                createCards();
            };
            
            ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                if (message.type === 'tick') {
                    updateCard(message.symbol, message.data);
                }
            };
            
            ws.onclose = () => {
                console.log('WebSocket disconnected');
                document.getElementById('status').innerHTML = '🔴 WebSocket disconnected - reconnecting...';
                setTimeout(connect, 3000);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                document.getElementById('status').innerHTML = '⚠️ WebSocket error';
            };
        }
        
        function subscribeToSymbols() {
            symbols.forEach(symbol => {
                ws.send(JSON.stringify({action: 'subscribe', symbol: symbol}));
            });
        }
        
        function createCards() {
            const dashboard = document.getElementById('dashboard');
            dashboard.innerHTML = '';
            
            symbols.forEach(symbol => {
                const card = document.createElement('div');
                card.className = 'symbol-card';
                card.id = `card-${symbol}`;
                card.innerHTML = `
                    <div class="symbol-name">${symbol}</div>
                    <div class="price-grid">
                        <div class="price-item">
                            <div>BID</div>
                            <div class="price-value bid" id="bid-${symbol}">--.-----</div>
                        </div>
                        <div class="price-item">
                            <div>ASK</div>
                            <div class="price-value ask" id="ask-${symbol}">--.-----</div>
                        </div>
                        <div class="price-item">
                            <div>SPREAD</div>
                            <div class="price-value spread" id="spread-${symbol}">-- pips</div>
                        </div>
                    </div>
                `;
                dashboard.appendChild(card);
            });
        }
        
        function updateCard(symbol, data) {
            document.getElementById(`bid-${symbol}`).textContent = data.bid.toFixed(5);
            document.getElementById(`ask-${symbol}`).textContent = data.ask.toFixed(5);
            document.getElementById(`spread-${symbol}`).textContent = `${data.spread_pips} pips`;
        }
        
        async function startStream() {
            try {
                const response = await fetch('/start-stream');
                const result = await response.json();
                document.getElementById('status').innerHTML = `🚀 ${result.message}`;
            } catch (error) {
                document.getElementById('status').innerHTML = `❌ Error: ${error.message}`;
            }
        }
        
        async function refreshData() {
            try {
                const response = await fetch('/status');
                const status = await response.json();
                document.getElementById('status').innerHTML = 
                    `📊 Streaming: ${status.streaming} | Clients: ${status.clients} | Keys: ${status.stream_keys}`;
            } catch (error) {
                document.getElementById('status').innerHTML = `❌ Error: ${error.message}`;
            }
        }
        
        async function checkHealth() {
            try {
                const response = await fetch('/health');
                const health = await response.json();
                document.getElementById('status').innerHTML = 
                    `💊 Health: ${health.status} | Redis: ${health.redis} | MT5: ${health.mt5}`;
            } catch (error) {
                document.getElementById('status').innerHTML = `❌ Health check failed: ${error.message}`;
            }
        }
        
        // Auto-connect when page loads
        window.onload = connect;
    </script>
</body>
</html>
EOF

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Copy your existing files to the new structure:"
echo "   - Copy websocket_streamer.py to websocket_streamer.py"
echo "   - Copy stream_creator_docker.py to stream_creator_docker.py"
echo ""
echo "2. Build and start the services:"
echo "   docker-compose up --build"
echo ""
echo "3. Access your dashboard:"
echo "   http://localhost:8010"
echo ""
echo "4. Optional: Start the stream creator:"
echo "   docker-compose --profile stream-creator up"
echo ""
echo "🎯 Services will be available at:"
echo "   - Dashboard: http://localhost:8010"
echo "   - Trading Backend: http://localhost:8009"
echo "   - MT5 VNC: http://localhost:3000"
echo "   - Redis: localhost:6382"
EOF

chmod +x setup_docker_dashboard.sh