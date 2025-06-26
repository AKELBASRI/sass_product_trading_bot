# trading_system_core.py
"""
Core configuration and utility functions for the trading system
Converted from MQL5 to Python
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union
from enum import Enum


class PositionType(Enum):
    """Position types matching MQL5"""
    BUY = 1
    SELL = -1
    NONE = 0


class OrderType(Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass
class TradingConfig:
    """Main configuration for the trading system"""
    # Risk Management
    max_risk_percent: float = 5.0
    min_risk_percent: float = 5.0
    maximum_sl_pips: float = 70.0
    max_daily_loss: float = 90.0
    max_daily_profit: float = 400.0
    enable_daily_limits: bool = False
    
    # Position Management
    partial_take_profit_pips: float = 15.0
    partial_close_loss_pips: float = 15.0
    partial_close_percent: float = 50.0
    enable_breakeven: bool = True
    enable_partial_close_profit: bool = False
    enable_partial_close_loss: bool = False
    breakeven_buffer_pips: float = 5.0
    early_exit_close_percent: float = 50.0
    
    # Trailing Stop
    enable_trailing_stop: bool = True
    trailing_timeframe: str = "1T"  # 1 minute
    
    # Session Trading
    allow_all_sessions: bool = True
    trade_pre_asian: bool = True
    trade_asian: bool = True
    trade_pre_london: bool = True
    trade_london_open: bool = True
    trade_pre_newyork: bool = True
    trade_newyork_open: bool = True
    trade_london_close: bool = True
    
    # Indicators
    min_pips_for_range: float = 30.0
    show_range_labels: bool = True
    min_retrace_percent: float = 30.0
    min_wick_size_percent: float = 0.3
    
    # Debug
    print_market_sessions: bool = False
    print_trend_direction: bool = False
    print_candle_indicator: bool = False
    print_level_id: bool = False
    print_sr_cycle: bool = False
    print_scenario_details: bool = True
    print_debug_info: bool = False
    print_risk_info: bool = False
    enable_debug: bool = False
    
    # Re-entry
    reentry: bool = True
    
    # Scenario specific
    default_target_pips: int = 250
    
    # Timeframes
    timeframe_early_exit: str = "10T"  # 10 minutes


@dataclass
class Position:
    """Represents an open position"""
    ticket: int
    symbol: str
    position_type: PositionType
    open_price: float
    volume: float
    stop_loss: float
    take_profit: float
    open_time: datetime
    profit: float = 0.0
    
    # Tracking flags
    partial_close_executed: bool = False
    partial_close_loss_executed: bool = False
    early_exit_executed: bool = False
    breakeven_hit: bool = False
    trailing_stop_activated: bool = False
    
    # Re-entry tracking
    original_volume: float = 0.0
    reentry_executed: bool = False
    reentry_ticket: Optional[int] = None


@dataclass
class Trade:
    """Represents a trade to be executed"""
    symbol: str
    trade_type: PositionType
    volume: float
    stop_loss: float
    take_profit: float
    comment: str = ""


class CandleUtils:
    """Utility functions for candle analysis"""
    
    @staticmethod
    def is_bullish_candle(df: pd.DataFrame, index: int) -> bool:
        """Check if a candle is bullish (close > open)"""
        if index < 0 or index >= len(df):
            return False
        return df.iloc[index]['close'] > df.iloc[index]['open']
    
    @staticmethod
    def is_bearish_candle(df: pd.DataFrame, index: int) -> bool:
        """Check if a candle is bearish (close < open)"""
        if index < 0 or index >= len(df):
            return False
        return df.iloc[index]['close'] < df.iloc[index]['open']
    
    @staticmethod
    def get_body_size(df: pd.DataFrame, index: int) -> float:
        """Get the body size of a candle"""
        if index < 0 or index >= len(df):
            return 0.0
        return abs(df.iloc[index]['close'] - df.iloc[index]['open'])
    
    @staticmethod
    def get_upper_wick_size(df: pd.DataFrame, index: int) -> float:
        """Get the upper wick size of a candle"""
        if index < 0 or index >= len(df):
            return 0.0
        row = df.iloc[index]
        return row['high'] - max(row['open'], row['close'])
    
    @staticmethod
    def get_lower_wick_size(df: pd.DataFrame, index: int) -> float:
        """Get the lower wick size of a candle"""
        if index < 0 or index >= len(df):
            return 0.0
        row = df.iloc[index]
        return min(row['open'], row['close']) - row['low']
    
    @staticmethod
    def has_upper_wick(df: pd.DataFrame, index: int, min_size: float = 0.0) -> bool:
        """Check if candle has upper wick of minimum size"""
        return CandleUtils.get_upper_wick_size(df, index) > min_size
    
    @staticmethod
    def has_lower_wick(df: pd.DataFrame, index: int, min_size: float = 0.0) -> bool:
        """Check if candle has lower wick of minimum size"""
        return CandleUtils.get_lower_wick_size(df, index) > min_size


class PriceUtils:
    """Utility functions for price calculations"""
    
    @staticmethod
    def calculate_pip_difference(price1: float, price2: float, pip_size: float = 0.0001) -> float:
        """Calculate pip difference between two price levels"""
        return abs(price1 - price2) / pip_size
    
    @staticmethod
    def pips_to_price(pips: float, pip_size: float = 0.0001) -> float:
        """Convert pips to price difference"""
        return pips * pip_size
    
    @staticmethod
    def calculate_lot_size(risk_amount: float, stop_loss_pips: float, 
                          pip_value: float = 10.0, min_lot: float = 0.01,
                          max_lot: float = 100.0, lot_step: float = 0.01) -> float:
        """Calculate position size based on risk"""
        if stop_loss_pips <= 0:
            return min_lot
            
        lot_size = risk_amount / (stop_loss_pips * pip_value)
        
        # Round to lot step
        lot_size = round(lot_size / lot_step) * lot_step
        
        # Apply limits
        return max(min_lot, min(max_lot, lot_size))


class TimeUtils:
    """Utility functions for time operations"""
    
    @staticmethod
    def is_new_bar(df: pd.DataFrame, last_processed_time: Optional[datetime], 
                   current_index: int) -> bool:
        """Check if we have a new bar"""
        if current_index < 0 or current_index >= len(df):
            return False
            
        current_time = df.index[current_index]
        return last_processed_time is None or current_time > last_processed_time
    
    @staticmethod
    def get_session_times(date: datetime, session_start: str, session_end: str) -> Tuple[datetime, datetime]:
        """Convert session time strings to datetime objects"""
        start_hour, start_min = map(int, session_start.split(':'))
        end_hour, end_min = map(int, session_end.split(':'))
        
        start_dt = date.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        end_dt = date.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        
        # Handle overnight sessions
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
            
        return start_dt, end_dt
    
    @staticmethod
    def is_in_session(current_time: datetime, start_time: str, end_time: str) -> bool:
        """Check if current time is within a session"""
        # Get today's session times
        today = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        session_start, session_end = TimeUtils.get_session_times(today, start_time, end_time)
        
        # Check if in today's session
        if session_start <= current_time <= session_end:
            return True
            
        # Check yesterday's session for overnight sessions
        if session_end.date() > session_start.date():
            yesterday = today - timedelta(days=1)
            session_start, session_end = TimeUtils.get_session_times(yesterday, start_time, end_time)
            if session_start <= current_time <= session_end:
                return True
                
        return False


def create_sample_dataframe(days: int = 30) -> pd.DataFrame:
    """Create a sample DataFrame for testing"""
    # Generate datetime index
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Create 15-minute intervals
    date_range = pd.date_range(start=start_date, end=end_date, freq='15T')
    
    # Generate random OHLCV data
    np.random.seed(42)
    
    df = pd.DataFrame(index=date_range)
    
    # Generate realistic price movements
    base_price = 1.1000
    df['close'] = base_price + np.cumsum(np.random.randn(len(date_range)) * 0.0001)
    
    # Generate OHLC from close
    df['open'] = df['close'].shift(1).fillna(base_price)
    df['high'] = df[['open', 'close']].max(axis=1) + abs(np.random.randn(len(date_range)) * 0.0002)
    df['low'] = df[['open', 'close']].min(axis=1) - abs(np.random.randn(len(date_range)) * 0.0002)
    df['volume'] = np.random.randint(1000, 10000, size=len(date_range))
    
    return df


# Example usage
if __name__ == "__main__":
    # Create configuration
    config = TradingConfig()
    
    # Create sample data
    df = create_sample_dataframe(days=5)
    
    print("Sample DataFrame:")
    print(df.head())
    print(f"\nDataFrame shape: {df.shape}")
    
    # Test candle utilities
    print(f"\nIs first candle bullish? {CandleUtils.is_bullish_candle(df, 0)}")
    print(f"First candle body size: {CandleUtils.get_body_size(df, 0):.5f}")
    
    # Test price utilities
    price_diff = PriceUtils.calculate_pip_difference(1.1050, 1.1000)
    print(f"\nPip difference between 1.1050 and 1.1000: {price_diff}")
    
    # Test time utilities
    now = datetime.now()
    in_london = TimeUtils.is_in_session(now, "08:00", "11:00")
    print(f"\nIs current time in London session? {in_london}")
