#!/usr/bin/env python3
# sync_all_symbols.py
"""
Synchronize all symbol data from MT5 to Redis
This ensures the dashboard has data for all symbols
"""

import redis
import json
import time
import logging
from datetime import datetime
from mt5linux import MetaTrader5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultiSymbolSync:
    def __init__(self):
        # Redis connection
        self.redis_client = redis.Redis(host='localhost', port=6382, decode_responses=True)
        
        # MT5 connection (adjust host based on your setup)
        self.mt5 = MetaTrader5(host='localhost', port=8001)
        
        # Symbols to sync
        self.symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD']
        
        # Timeframes to sync (in minutes)
        self.timeframes = {
            1: self.mt5.TIMEFRAME_M1,
            5: self.mt5.TIMEFRAME_M5,
            15: self.mt5.TIMEFRAME_M15,
            30: self.mt5.TIMEFRAME_M30,
            60: self.mt5.TIMEFRAME_H1,
            240: self.mt5.TIMEFRAME_H4,
            1440: self.mt5.TIMEFRAME_D1
        }
    
    def connect_mt5(self):
        """Connect to MT5"""
        if not self.mt5.initialize():
            logger.error("Failed to initialize MT5")
            return False
        
        logger.info("Connected to MT5")
        return True
    
    def sync_symbol_data(self, symbol: str):
        """Sync all timeframes for a symbol"""
        logger.info(f"Syncing {symbol}...")
        
        # Check if symbol is available
        symbol_info = self.mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.warning(f"{symbol} not found")
            return
        
        # Enable symbol if not visible
        if not symbol_info.visible:
            if not self.mt5.symbol_select(symbol, True):
                logger.warning(f"Failed to select {symbol}")
                return
        
        # Sync each timeframe
        for minutes, mt5_timeframe in self.timeframes.items():
            try:
                # Get OHLC data
                rates = self.mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, 1000)
                
                if rates is not None and len(rates) > 0:
                    # Convert to format expected by dashboard
                    ohlc_data = {
                        'time': [datetime.fromtimestamp(r['time']).isoformat() for r in rates],
                        'open': [float(r['open']) for r in rates],
                        'high': [float(r['high']) for r in rates],
                        'low': [float(r['low']) for r in rates],
                        'close': [float(r['close']) for r in rates],
                        'volume': [int(r['tick_volume']) for r in rates]
                    }
                    
                    # Store in Redis
                    key = f"mt5:ohlc:{symbol}:{minutes}"
                    self.redis_client.set(key, json.dumps(ohlc_data), ex=300)
                    
                    logger.info(f"✓ {symbol} {minutes}M: {len(rates)} bars")
                else:
                    logger.warning(f"✗ {symbol} {minutes}M: No data")
                    
            except Exception as e:
                logger.error(f"Error syncing {symbol} {minutes}M: {e}")
        
        # Get and store current tick
        try:
            tick = self.mt5.symbol_info_tick(symbol)
            if tick:
                self.redis_client.hset(f'mt5:tick:{symbol}', mapping={
                    'bid': tick.bid,
                    'ask': tick.ask,
                    'last': tick.last,
                    'volume': tick.volume,
                    'time': datetime.fromtimestamp(tick.time).isoformat()
                })
                logger.info(f"✓ {symbol} tick: Bid={tick.bid}, Ask={tick.ask}")
        except Exception as e:
            logger.error(f"Error getting tick for {symbol}: {e}")
    
    def run_continuous_sync(self, interval: int = 60):
        """Run continuous synchronization"""
        logger.info(f"Starting continuous sync (interval: {interval}s)")
        
        while True:
            try:
                # Sync all symbols
                for symbol in self.symbols:
                    self.sync_symbol_data(symbol)
                
                # Update status
                self.redis_client.hset('mt5:sync:status', mapping={
                    'last_sync': datetime.now().isoformat(),
                    'symbols_count': len(self.symbols),
                    'status': 'running'
                })
                
                logger.info(f"Sync complete. Waiting {interval}s...")
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Sync stopped by user")
                break
            except Exception as e:
                logger.error(f"Sync error: {e}")
                time.sleep(10)
    
    def test_redis_data(self):
        """Test what data is available in Redis"""
        print("\n=== Testing Redis Data ===")
        
        for symbol in self.symbols:
            print(f"\n{symbol}:")
            
            # Check tick data
            tick = self.redis_client.hget(f'mt5:tick:{symbol}', 'bid')
            if tick:
                print(f"  ✓ Tick data: Bid = {tick}")
            else:
                print(f"  ✗ No tick data")
            
            # Check OHLC data
            for tf in [1, 5, 15, 30, 60]:
                key = f"mt5:ohlc:{symbol}:{tf}"
                if self.redis_client.exists(key):
                    data = json.loads(self.redis_client.get(key))
                    print(f"  ✓ {tf}M: {len(data.get('time', []))} bars")
                else:
                    print(f"  ✗ {tf}M: No data")

if __name__ == "__main__":
    sync = MultiSymbolSync()
    
    # Connect to MT5
    if not sync.connect_mt5():
        print("Failed to connect to MT5")
        exit(1)
    
    # Add option to test or run continuous
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        # Just test once
        for symbol in sync.symbols:
            sync.sync_symbol_data(symbol)
        sync.test_redis_data()
    else:
        # Run continuous sync
        sync.run_continuous_sync(interval=30)
