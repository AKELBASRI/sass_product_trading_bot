import asyncio
import json
import logging
import time
import os  # Add this import
from datetime import datetime
from typing import Dict, Any, List, Optional
import redis
import uvicorn
import pandas as pd  # <-- ADD THIS IMPORT
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemStatus(BaseModel):
    running: bool
    last_update: str
    current_time: str
    error: Optional[str] = None
    redis_connected: bool = False
    mt5_connected: bool = False
    active_symbols: List[str] = []

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    components: Dict[str, bool]
    details: Dict[str, Any]

class OHLCData(BaseModel):
    symbol: str
    timeframe: str
    data: List[Dict[str, Any]]
    count: int

class CandleData(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int

class WorkingBackend:
    def __init__(self):
        try:
            # Use environment variables or Docker service names
            redis_host = os.getenv('REDIS_HOST', 'redis')  # Default to 'redis' service name
            redis_port = int(os.getenv('REDIS_PORT', 6379))  # Default to internal port 6379
            
            logger.info(f"Attempting to connect to Redis at {redis_host}:{redis_port}")
            
            self.redis_client = redis.Redis(
                host=redis_host, 
                port=redis_port, 
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Test the connection
            self.redis_client.ping()
            logger.info(f"Successfully connected to Redis at {redis_host}:{redis_port}")
            self.redis_connected = True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_connected = False
        
        self.is_running = False
        self.last_update = datetime.now()
        self.error_message = None
        
        # Check for MT5 data directly
        self.mt5_data_available = self._check_mt5_data()
        logger.info(f"MT5 data available: {self.mt5_data_available}")
    
    def _check_mt5_data(self):
        """Check if MT5 data exists in Redis"""
        try:
            if self.redis_connected:
                ohlc_keys = self.redis_client.keys("mt5:ohlc:*")
                logger.info(f"Found {len(ohlc_keys)} MT5 OHLC keys")
                return len(ohlc_keys) > 0
            return False
        except Exception as e:
            logger.error(f"Error checking MT5 data: {e}")
            return False
   
    async def start(self):
        self.is_running = True
        self.error_message = None
        self.last_update = datetime.now()
        logger.info("Trading system started")
    
    async def stop(self):
        self.is_running = False
        logger.info("Trading system stopped")
    
    def get_status(self):
        return {
            "running": self.is_running,
            "last_update": self.last_update.isoformat(),
            "current_time": datetime.now().isoformat(),
            "error": self.error_message,
            "redis_connected": self.redis_connected,
            "mt5_connected": self.mt5_data_available,
            "active_symbols": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD"] if self.mt5_data_available else []
        }
    
    def get_health(self):
        # Get OHLC keys directly
        ohlc_keys = []
        if self.redis_connected:
            try:
                ohlc_keys = self.redis_client.keys("mt5:ohlc:*")
            except:
                pass
        
        return {
            "status": "healthy" if self.redis_connected and self.mt5_data_available else "degraded",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "redis": self.redis_connected,
                "mt5": self.mt5_data_available,
                "system": self.is_running
            },
            "details": {
                "redis": {
                    "connected": self.redis_connected,
                    "keys": self.redis_client.keys("*")[:20] if self.redis_connected else [],
                },
                "mt5": {
                    "data_available": self.mt5_data_available,
                    "ohlc_keys": ohlc_keys
                },
                "system": {
                    "running": self.is_running,
                    "last_update": self.last_update.isoformat()
                }
            }
        }
    
    def get_available_symbols(self):
        """Get all available symbols from Redis OHLC data"""
        try:
            if not self.redis_connected:
                return []
            
            ohlc_keys = self.redis_client.keys("mt5:ohlc:*")
            symbols = set()
            for key in ohlc_keys:
                # Extract symbol from key format: mt5:ohlc:SYMBOL:TIMEFRAME
                parts = key.split(":")
                if len(parts) >= 3:
                    symbols.add(parts[2])
            return list(symbols)
        except Exception as e:
            logger.error(f"Error getting symbols: {e}")
            return []

    def get_ohlc_data(self, symbol: str, timeframe: str = "15", limit: int = 100):
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

    def get_ohlc_dataframe(self, symbol: str, timeframe: str = "15", limit: int = 100):
        """Get OHLC data as pandas DataFrame"""
        try:
            # Get the processed OHLC data
            ohlc_data = self.get_ohlc_data(symbol, timeframe, limit)
            
            if not ohlc_data["data"]:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(ohlc_data["data"])
            
            # Ensure proper timestamp handling
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Ensure numeric columns
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Sort by timestamp
            if 'timestamp' in df.columns:
                df = df.sort_values('timestamp')
                df = df.reset_index(drop=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error creating DataFrame: {e}")
            return pd.DataFrame()

    def redis_test(self):
        if not self.redis_connected:
            raise HTTPException(status_code=503, detail="Redis not connected")
        
        try:
            all_keys = self.redis_client.keys("*")
            mt5_keys = [k for k in all_keys if k.startswith("mt5:")]
            ohlc_keys = [k for k in all_keys if "mt5:ohlc" in k]
            
            # Test write/read
            test_key = "test_key"
            test_value = f"test_{datetime.now().isoformat()}"
            self.redis_client.set(test_key, test_value, ex=60)
            retrieved = self.redis_client.get(test_key)
            
            return {
                "connected": True,
                "keys": all_keys[:50],
                "test_write": True,
                "test_read": retrieved == test_value,
                "mt5_data_keys": ohlc_keys,
                "mt5_all_keys": mt5_keys[:10]
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}

# FastAPI app
app = FastAPI(title="Working Trading Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

backend = WorkingBackend()

@app.get("/status", response_model=SystemStatus)
async def get_status():
    status_data = backend.get_status()
    return SystemStatus(**status_data)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    health_data = backend.get_health()
    return HealthResponse(**health_data)

@app.post("/start")
async def start_system():
    await backend.start()
    return {"message": "System started"}

@app.post("/stop")
async def stop_system():
    await backend.stop()
    return {"message": "System stopped"}

@app.get("/redis-test")
async def redis_test():
    return backend.redis_test()

@app.get("/symbols")
async def get_symbols():
    """Get all available trading symbols"""
    symbols = backend.get_available_symbols()
    return {"symbols": symbols, "count": len(symbols)}

@app.get("/ohlc/{symbol}", response_model=OHLCData)
async def get_ohlc(symbol: str, timeframe: str = "15", limit: int = 100):
    """Get OHLC data for a specific symbol"""
    return backend.get_ohlc_data(symbol.upper(), timeframe, limit)

@app.get("/ohlc/{symbol}/dataframe")
async def get_ohlc_dataframe(symbol: str, timeframe: str = "15", limit: int = 100):
    """Get OHLC data as DataFrame (JSON format)"""
    df = backend.get_ohlc_dataframe(symbol.upper(), timeframe, limit)
    
    if df.empty:
        return {"error": "No data available", "symbol": symbol, "timeframe": timeframe}
    
    # Convert DataFrame to JSON
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "data": df.to_dict('records'),
        "columns": df.columns.tolist(),
        "shape": df.shape,
        "stats": {
            "count": len(df),
            "latest_price": float(df['close'].iloc[-1]) if 'close' in df.columns and len(df) > 0 else None,
            "price_change": float(df['close'].iloc[-1] - df['close'].iloc[0]) if 'close' in df.columns and len(df) > 1 else None,
            "high_24h": float(df['high'].max()) if 'high' in df.columns else None,
            "low_24h": float(df['low'].min()) if 'low' in df.columns else None
        }
    }

@app.get("/redis-keys")
async def get_redis_keys():
    """Debug endpoint to see all Redis keys"""
    if not backend.redis_connected:
        raise HTTPException(status_code=503, detail="Redis not connected")
    
    try:
        all_keys = backend.redis_client.keys("*")
        mt5_keys = [k for k in all_keys if k.startswith("mt5:")]
        ohlc_keys = [k for k in all_keys if "mt5:ohlc" in k]
        
        return {
            "total_keys": len(all_keys),
            "all_keys": all_keys[:50],  # First 50 keys
            "mt5_keys": mt5_keys,
            "ohlc_keys": ohlc_keys
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug-raw/{symbol}")
async def debug_raw_data(symbol: str, timeframe: str = "15"):
    """Debug endpoint to see raw Redis data"""
    if not backend.redis_connected:
        raise HTTPException(status_code=503, detail="Redis not connected")
    
    key = f"mt5:ohlc:{symbol}:{timeframe}"
    raw_data = backend.redis_client.get(key)
    
    if not raw_data:
        return {"error": f"No data found for key: {key}"}
    
    try:
        # Try to parse as JSON
        parsed = json.loads(raw_data)
        return {
            "key": key,
            "data_type": type(parsed).__name__,
            "keys": list(parsed.keys()) if isinstance(parsed, dict) else "not_dict",
            "sample": {k: (list(v.keys())[:5] if isinstance(v, dict) else str(v)[:100]) for k, v in list(parsed.items())[:3]} if isinstance(parsed, dict) else str(parsed)[:500],
            "data_length": len(parsed) if hasattr(parsed, '__len__') else "unknown"
        }
    except json.JSONDecodeError:
        return {
            "key": key,
            "data_type": "string",
            "length": len(raw_data),
            "sample": raw_data[:200]
        }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8009, log_level="info")