#!/bin/bash
echo "🚀 Setting up Real-Time Trading Data Stream"

# Create WebSocket streamer
cat > websocket_streamer.py << 'PYEOF'
#!/usr/bin/env python3
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Set, Dict, Any
import redis
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from mt5linux import MetaTrader5

logging.basicConfig(level=logging.INFO)
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
    
    async def broadcast_tick(self, symbol: str, tick_data: Dict[str, Any]):
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
                except:
                    disconnected.add(websocket)
        
        for websocket in disconnected:
            self.disconnect(websocket)

class TickDataStreamer:
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6382, decode_responses=True)
        self.mt5 = None
        self.running = False
        self.symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD']
        self.connection_manager = ConnectionManager()
        self.last_prices = {}
        
    async def connect_mt5(self):
        try:
            self.mt5 = MetaTrader5(host='localhost', port=8001)
            if self.mt5.initialize():
                return True
        except Exception as e:
            logger.error(f"MT5 error: {e}")
        return False
    
    async def start_streaming(self):
        if not await self.connect_mt5():
            return
        
        self.running = True
        logger.info("Starting streaming...")
        
        while self.running:
            try:
                for symbol in self.symbols:
                    if not self.running:
                        break
                    
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
                            'spread_pips': round((tick.ask - tick.bid) * 10000, 1),
                            'timestamp': int(tick.time),
                            'price_change': round(price_change, 5),
                            'price_change_pct': round(price_change_pct, 4),
                            'trend': "up" if price_change > 0 else "down" if price_change < 0 else "neutral"
                        }
                        
                        await self.connection_manager.broadcast_tick(symbol, tick_data)
                        self.last_prices[symbol] = current_price
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                await asyncio.sleep(1)

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

streamer = TickDataStreamer()

@app.get("/")
async def serve_dashboard():
    return FileResponse("dashboard.html")

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
    except WebSocketDisconnect:
        streamer.connection_manager.disconnect(websocket)

@app.get("/start-stream")
async def start_stream():
    if not streamer.running:
        asyncio.create_task(streamer.start_streaming())
        return {"message": "Streaming started"}
    return {"message": "Already running"}

@app.get("/stop-stream")
async def stop_stream():
    streamer.running = False
    return {"message": "Streaming stopped"}

@app.get("/status")
async def get_status():
    return {
        "streaming": streamer.running,
        "clients": len(streamer.connection_manager.active_connections),
        "symbols": streamer.symbols
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8010)
PYEOF

echo "✅ WebSocket streamer created!"
