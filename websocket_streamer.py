#!/usr/bin/env python3
"""
WebSocket Streamer for Docker Environment
"""

import asyncio
import json
import logging
import time
import os
from datetime import datetime, timezone
from typing import Set, Dict, Any
from contextlib import asynccontextmanager

import redis
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from mt5linux import MetaTrader5

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set()
        logger.info(f"Client connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)
        logger.info(f"Client disconnected. Total: {len(self.active_connections)}")
    
    async def subscribe(self, websocket: WebSocket, symbol: str):
        if websocket in self.subscriptions:
            self.subscriptions[websocket].add(symbol)
            logger.info(f"Client subscribed to {symbol}")
    
    async def broadcast_tick(self, symbol: str, tick_data: Dict[str, Any]):
        if not self.active_connections:
            return
            
        message = {
            "type": "tick",
            "symbol": symbol,
            "data": tick_data,
            "timestamp": int(time.time() * 1000)
        }
        
        disconnected = set()
        for websocket in self.active_connections:
            if symbol in self.subscriptions.get(websocket, set()):
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to client: {e}")
                    disconnected.add(websocket)
        
        for websocket in disconnected:
            self.disconnect(websocket)

class TickDataStreamer:
    def __init__(self):
        # Use environment variables for Docker
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        mt5_host = os.getenv('MT5_HOST', 'localhost')
        mt5_port = int(os.getenv('MT5_PORT', 8001))
        
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        self.mt5_host = mt5_host
        self.mt5_port = mt5_port
        self.mt5 = None
        self.running = False
        self.symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']
        self.connection_manager = ConnectionManager()
        self.last_prices = {}
        
        logger.info(f"Initialized with Redis: {redis_host}:{redis_port}, MT5: {mt5_host}:{mt5_port}")
        
    async def connect_mt5(self, max_retries=5, retry_delay=5):
        """
        Connect to MT5 with retry mechanism
        """
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Attempting to connect to MT5 ({attempt}/{max_retries}): {self.mt5_host}:{self.mt5_port}")
                self.mt5 = MetaTrader5(host=self.mt5_host, port=self.mt5_port)
                if self.mt5.initialize():
                    account = self.mt5.account_info()
                    logger.info(f"MT5 connected successfully: {account.login} - {account.server}")
                    return True
                else:
                    logger.error(f"MT5 initialization failed (attempt {attempt}/{max_retries})")
            except Exception as e:
                logger.error(f"MT5 connection error (attempt {attempt}/{max_retries}): {e}")
            
            if attempt < max_retries:
                logger.info(f"Retrying MT5 connection in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
        
        logger.error(f"Failed to connect to MT5 after {max_retries} attempts")
        return False
    
    async def start_streaming(self):
        """
        Start streaming tick data from MT5 to WebSocket clients
        """
        # Try to connect to MT5 with retries
        if not await self.connect_mt5(max_retries=10, retry_delay=5):
            logger.error("Failed to connect to MT5 for streaming after multiple attempts")
            return
        
        self.running = True
        logger.info("Starting tick data streaming...")
        
        iteration = 0
        reconnect_attempts = 0
        max_reconnect_attempts = 5
        
        while self.running:
            try:
                iteration += 1
                
                # Check MT5 connection and reconnect if needed
                if not self.mt5 or not hasattr(self.mt5, 'symbol_info_tick'):
                    if reconnect_attempts < max_reconnect_attempts:
                        reconnect_attempts += 1
                        logger.warning(f"MT5 connection lost. Attempting to reconnect ({reconnect_attempts}/{max_reconnect_attempts})")
                        if await self.connect_mt5(max_retries=3, retry_delay=2):
                            reconnect_attempts = 0  # Reset counter on successful reconnect
                        else:
                            await asyncio.sleep(5)  # Wait before next reconnect attempt
                        continue
                    else:
                        logger.error(f"Failed to reconnect to MT5 after {max_reconnect_attempts} attempts")
                        self.running = False
                        break
                
                for symbol in self.symbols:
                    if not self.running:
                        break
                    
                    try:
                        tick = self.mt5.symbol_info_tick(symbol)
                        if tick:
                            current_price = tick.bid
                            last_price = self.last_prices.get(symbol, current_price)
                            price_change = current_price - last_price
                            price_change_pct = (price_change / last_price * 100) if last_price != 0 else 0
                            
                            tick_data = {
                                'symbol': symbol,
                                'bid': float(tick.bid),
                                'ask': float(tick.ask),
                                'spread': float(tick.ask - tick.bid),
                                'spread_pips': round((tick.ask - tick.bid) * 10000, 1),
                                'timestamp': int(tick.time),
                                'datetime': datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
                                'price_change': round(price_change, 5),
                                'price_change_pct': round(price_change_pct, 4),
                                'trend': "up" if price_change > 0.00001 else "down" if price_change < -0.00001 else "neutral",
                                'created_at': int(time.time()),
                                'iteration': iteration
                            }
                            
                            # Store in Redis
                            stream_key = f"mt5:stream:{symbol}:latest"
                            self.redis_client.set(stream_key, json.dumps(tick_data), ex=300)  # 5 min expiry
                            
                            # Broadcast to WebSocket clients
                            await self.connection_manager.broadcast_tick(symbol, tick_data)
                            
                            # Update last price
                            self.last_prices[symbol] = current_price
                    except Exception as e:
                        logger.warning(f"Error processing symbol {symbol}: {e}")
                
                # Log status every 60 iterations
                if iteration % 60 == 0:
                    logger.info(f"Streaming iteration {iteration}, clients: {len(self.connection_manager.active_connections)}")
                
                await asyncio.sleep(1)  # 1 second between updates
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                await asyncio.sleep(2)
        
        logger.info("Streaming loop ended")
    
    def stop_streaming(self):
        self.running = False
        if self.mt5:
            self.mt5.shutdown()
        logger.info("Streaming stopped")

# Create the streamer instance
streamer = TickDataStreamer()

# FastAPI app setup with lifespan for proper lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create the streaming task when the app starts
    streaming_task = asyncio.create_task(streamer.start_streaming())
    yield
    # Shutdown: stop the streaming when the app shuts down
    streamer.stop_streaming()
    # Wait for the streaming task to complete if it's still running
    if not streaming_task.done():
        streaming_task.cancel()
        try:
            await streaming_task
        except asyncio.CancelledError:
            pass

# Create the FastAPI app with lifespan
app = FastAPI(
    title="Trading WebSocket Streamer", 
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static dashboard files
dashboard_path = "/app/dashboard"
if os.path.exists(dashboard_path):
    app.mount("/static", StaticFiles(directory=dashboard_path), name="static")

@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard"""
    # Try multiple dashboard file locations
    dashboard_files = [
        "/app/dashboard/index.html",
        "/app/working_dashboard.html",
        "/app/simple_dashboard.html"
    ]
    
    for dashboard_file in dashboard_files:
        if os.path.exists(dashboard_file):
            return FileResponse(dashboard_file)
    
    # Return built-in dashboard if no file found
    return HTMLResponse(content="""
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

    <div id="status">🟢 WebSocket Streamer Running</div>

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
</html>""")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await streamer.connection_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("action") == "subscribe":
                symbol = data.get("symbol")
                if symbol:
                    await streamer.connection_manager.subscribe(websocket, symbol)
                    await websocket.send_json({
                        "type": "subscription_confirmed",
                        "symbol": symbol
                    })
    except WebSocketDisconnect:
        streamer.connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        streamer.connection_manager.disconnect(websocket)

@app.get("/start-stream")
async def start_stream():
    """Start the tick data streaming"""
    if not streamer.running:
        # Use asyncio.create_task to run streaming in background
        asyncio.create_task(streamer.start_streaming())
        return {"message": "Streaming started", "status": "success"}
    return {"message": "Streaming already running", "status": "info"}

@app.get("/stop-stream")
async def stop_stream():
    """Stop the tick data streaming"""
    streamer.stop_streaming()
    return {"message": "Streaming stopped", "status": "success"}

@app.get("/status")
async def get_status():
    """Get streaming status"""
    try:
        streamer.redis_client.ping()
        redis_connected = True
        stream_keys_count = len(streamer.redis_client.keys("mt5:stream:*"))
    except Exception as e:
        redis_connected = False
        stream_keys_count = 0
    
    return {
        "streaming": streamer.running,
        "clients": len(streamer.connection_manager.active_connections),
        "symbols": streamer.symbols,
        "redis_connected": redis_connected,
        "stream_keys": stream_keys_count,
        "last_prices": streamer.last_prices
    }

@app.get("/latest-tick/{symbol}")
async def get_latest_tick(symbol: str):
    """Get latest tick for a symbol"""
    try:
        # Try stream data first
        stream_key = f"mt5:stream:{symbol.upper()}:latest"
        data = streamer.redis_client.get(stream_key)
        if data:
            return {"symbol": symbol, "data": json.loads(data), "source": "stream"}
        
        # Fallback to tick data
        tick_key = f"mt5:tick:{symbol.upper()}:latest"
        tick_data = streamer.redis_client.get(tick_key)
        if tick_data:
            return {"symbol": symbol, "data": json.loads(tick_data), "source": "tick"}
            
        return {"symbol": symbol, "data": None, "message": "No recent data"}
    except Exception as e:
        logger.error(f"Error getting latest tick for {symbol}: {e}")
        return {"error": str(e)}

@app.get("/stream-keys")
async def get_stream_keys():
    """Debug: Show all stream keys"""
    try:
        stream_keys = streamer.redis_client.keys("mt5:stream:*:latest")
        result = {}
        for key in stream_keys:
            data = streamer.redis_client.get(key)
            if data:
                try:
                    result[key] = json.loads(data)
                except json.JSONDecodeError:
                    result[key] = data
        return result
    except Exception as e:
        logger.error(f"Error getting stream keys: {e}")
        return {"error": str(e)}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test Redis connection
        streamer.redis_client.ping()
        redis_status = True
        stream_keys_count = len(streamer.redis_client.keys("mt5:stream:*"))
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        redis_status = False
        stream_keys_count = 0
    
    # Test MT5 connection
    mt5_status = False
    try:
        if streamer.mt5 and streamer.running:
            mt5_status = True
        else:
            # Try a new connection
            test_mt5 = MetaTrader5(host=streamer.mt5_host, port=streamer.mt5_port)
            if test_mt5.initialize():
                mt5_status = True
                test_mt5.shutdown()
    except Exception as e:
        logger.error(f"MT5 health check failed: {e}")
    
    overall_status = "healthy" if (redis_status and mt5_status) else "degraded"
    
    return {
        "status": overall_status,
        "redis": redis_status,
        "mt5": mt5_status,
        "streaming": streamer.running,
        "clients": len(streamer.connection_manager.active_connections),
        "stream_keys": stream_keys_count,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    # Run the server with Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010, log_level="info")