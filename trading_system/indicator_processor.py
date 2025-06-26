# indicator_processor.py
"""
Main Indicator Processor
Integrates all technical indicators
Converted from IndicatorProcessor.mqh
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
from datetime import datetime

# Import all indicators
from .market_sessions import MarketSessionsIndicator
from .detect_candles import CandlePatternDetector
from .level_identification import LevelIdentification
from .supertrend import SuperTrend
from .trend_detector import TrendDetector
from .detect_range import RangeDetector
from .fresh_wicks import FreshWicksIndicator
from .candle_retracement import CandleRetracementIndicator
from .trading_system_core import TradingConfig, PriceUtils


class IndicatorProcessor:
    """
    Main processor that integrates all technical indicators
    """
    
    def __init__(self, config: TradingConfig):
        """
        Initialize the indicator processor with configuration
        
        Args:
            config: Trading system configuration
        """
        self.config = config
        
        # Initialize all indicators
        self.market_sessions = MarketSessionsIndicator()
        
        self.candle_detector = CandlePatternDetector(
            body_to_wick_ratio=0.5,
            minimum_wick_size_pips=5.0,
            large_wick_ratio=2.0
        )
        
        self.level_identification = LevelIdentification(
            min_pips=0.0  # Will use config value if needed
        )
        
        self.supertrend = SuperTrend(
            period=10,
            multiplier=3.0
        )
        
        self.trend_detector = TrendDetector(
            max_bars_to_process=1000
        )
        
        self.range_detector = RangeDetector(
            min_candles_in_range=3
        )
        
        self.fresh_wicks = FreshWicksIndicator(
            min_wick_size_atr=config.min_wick_size_percent,
            atr_period=20
        )
        
        self.candle_retracement = CandleRetracementIndicator(
            min_retrace_percent=config.min_retrace_percent
        )
        
        # Storage for processed data
        self.df_processed: Optional[pd.DataFrame] = None
        
        # Current state tracking
        self.current_levels = {
            'min_resistance': None,
            'max_resistance': None,
            'min_support': None,
            'max_support': None,
            'current_level_min': None,
            'current_level_max': None,
            'in_significant_range': False
        }
        
    def process_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process all indicators on the dataframe
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with all indicator values added
        """
        # Start with a copy
        result_df = df.copy()
        
        # 1. Market Sessions
        if self.config.print_market_sessions:
            print("Processing Market Sessions...")
        result_df = self.market_sessions.calculate(result_df)
        
        # 2. Candle Patterns
        if self.config.print_candle_indicator:
            print("Processing Candle Patterns...")
        result_df = self.candle_detector.detect_patterns(result_df)
        
        # 3. Support/Resistance Levels
        if self.config.print_level_id:
            print("Processing Support/Resistance Levels...")
        result_df = self.level_identification.calculate(result_df)
        
        # 4. SuperTrend
        if self.config.print_trend_direction:
            print("Processing SuperTrend...")
        result_df = self.supertrend.calculate(result_df)
        
        # 5. Trend Detector
        if self.config.print_trend_direction:
            print("Processing Trend Detector...")
        result_df = self.trend_detector.calculate(result_df)
        
        # 6. Range Detection
        if self.config.enable_debug:
            print("Processing Range Detection...")
        result_df = self.range_detector.calculate(result_df)
        
        # 7. Fresh Wicks
        result_df = self.fresh_wicks.calculate(result_df)
        
        # 8. Candle Retracement (Stop Loss levels)
        if self.config.print_sr_cycle:
            print("Processing Candle Retracement...")
        result_df = self.candle_retracement.calculate(result_df)
        
        # Update current levels
        self._update_current_levels(result_df)
        
        # Store processed dataframe
        self.df_processed = result_df
        
        return result_df
    
    def _update_current_levels(self, df: pd.DataFrame):
        """Update current support/resistance levels and range info"""
        # Get latest values
        last_idx = -1
        
        # Update from level identification
        self.current_levels['min_resistance'] = df['min_resistance'].iloc[last_idx] \
            if pd.notna(df['min_resistance'].iloc[last_idx]) else None
        self.current_levels['max_resistance'] = df['max_resistance'].iloc[last_idx] \
            if pd.notna(df['max_resistance'].iloc[last_idx]) else None
        self.current_levels['min_support'] = df['min_support'].iloc[last_idx] \
            if pd.notna(df['min_support'].iloc[last_idx]) else None
        self.current_levels['max_support'] = df['max_support'].iloc[last_idx] \
            if pd.notna(df['max_support'].iloc[last_idx]) else None
        
        # Calculate trading range
        self._calculate_and_label_ranges()
    
    def _calculate_and_label_ranges(self):
        """Calculate current trading range and check if price is within significant range"""
        # Check if we have valid levels
        if (self.current_levels['max_support'] is not None and 
            self.current_levels['min_resistance'] is not None):
            
            # Calculate range size
            range_pips = PriceUtils.calculate_pip_difference(
                self.current_levels['min_resistance'],
                self.current_levels['max_support']
            )
            
            # Check if range is significant
            if range_pips >= self.config.min_pips_for_range:
                self.current_levels['current_level_min'] = self.current_levels['max_support']
                self.current_levels['current_level_max'] = self.current_levels['min_resistance']
                self.current_levels['in_significant_range'] = True
                
                # Check if current price is within range
                if self.df_processed is not None:
                    current_price = self.df_processed['close'].iloc[-1]
                    if (current_price >= self.current_levels['current_level_min'] and
                        current_price <= self.current_levels['current_level_max']):
                        self.current_levels['price_in_range'] = True
                    else:
                        self.current_levels['price_in_range'] = False
            else:
                self.current_levels['in_significant_range'] = False
        else:
            self.current_levels['in_significant_range'] = False
    
    def is_trade_allowed_for_current_session(self, df: pd.DataFrame = None) -> bool:
        """Check if trading is allowed in current market session"""
        if df is None:
            df = self.df_processed
            
        if df is None:
            return False
            
        current_session = df['session'].iloc[-1]
        return self.market_sessions.is_trade_allowed(current_session)
    
    def get_current_session_info(self) -> Dict[str, Any]:
        """Get information about current market session"""
        if self.df_processed is None:
            return {}
            
        session_value = self.df_processed['session'].iloc[-1]
        session_name = self.market_sessions.get_session_name(session_value)
        trade_allowed = self.market_sessions.is_trade_allowed(session_value)
        
        return {
            'session_value': session_value,
            'session_name': session_name,
            'trade_allowed': trade_allowed
        }
    
    def get_trend_info(self) -> Dict[str, Any]:
        """Get current trend information from multiple sources"""
        if self.df_processed is None:
            return {}
            
        return {
            'supertrend': {
                'direction': self.supertrend.get_current_trend(self.df_processed),
                'level': self.df_processed['supertrend'].iloc[-1]
            },
            'trend_detector': {
                'direction': int(self.df_processed['trend'].iloc[-1]),
                'name': self.df_processed['trend_name'].iloc[-1]
            }
        }
    
    def get_candle_patterns(self, index: int = -1) -> Dict[str, bool]:
        """Get candle patterns for a specific bar"""
        if self.df_processed is None:
            return {}
            
        return self.candle_detector.get_pattern_summary(self.df_processed, index)
    
    def get_stop_loss_levels(self) -> Dict[str, Optional[float]]:
        """Get current stop loss levels from candle retracement"""
        if self.df_processed is None:
            return {'stoploss_up': None, 'stoploss_down': None}
            
        return self.candle_retracement.get_current_stop_levels(self.df_processed)
    
    def get_fresh_wick_levels(self) -> Dict[str, Optional[float]]:
        """Get current fresh wick levels"""
        if self.df_processed is None:
            return {'upper_wick': None, 'lower_wick': None}
            
        return self.fresh_wicks.get_current_fresh_wicks(self.df_processed)
    
    def is_in_range(self) -> bool:
        """Check if price is currently in a range"""
        if self.df_processed is None:
            return False
            
        return bool(self.df_processed['in_range'].iloc[-1])
    
    def get_range_info(self) -> Dict[str, Any]:
        """Get current range information"""
        if self.df_processed is None:
            return {}
            
        range_info = self.range_detector.get_current_range()
        
        # Add from dataframe
        if pd.notna(self.df_processed['range_high'].iloc[-1]):
            range_info['df_high'] = self.df_processed['range_high'].iloc[-1]
            range_info['df_low'] = self.df_processed['range_low'].iloc[-1]
            
        return range_info
    
    def calculate_pip_difference(self, price1: float, price2: float) -> float:
        """Calculate pip difference between two prices"""
        return PriceUtils.calculate_pip_difference(price1, price2)
    
    # Getter methods for compatibility with MQL5 code structure
    def get_max_support_m15(self) -> Optional[float]:
        """Get max support from M15 (using stored values)"""
        return self.current_levels.get('max_support')
    
    def get_max_support_m30(self) -> Optional[float]:
        """Get max support from M30 (same as M15 in this implementation)"""
        return self.current_levels.get('max_support')
    
    def get_min_resistance_15(self) -> Optional[float]:
        """Get min resistance from M15"""
        return self.current_levels.get('min_resistance')
    
    def get_min_resistance_30(self) -> Optional[float]:
        """Get min resistance from M30"""
        return self.current_levels.get('min_resistance')
    
    def get_current_level_min(self) -> Optional[float]:
        """Get current minimum level (support) for trading range"""
        return self.current_levels.get('current_level_min')
    
    def get_current_level_max(self) -> Optional[float]:
        """Get current maximum level (resistance) for trading range"""
        return self.current_levels.get('current_level_max')
    
    def is_in_significant_range(self) -> bool:
        """Check if price is in a significant trading range"""
        return self.current_levels.get('in_significant_range', False)
    
    def get_stop_loss_price_up(self) -> Optional[float]:
        """Get stop loss price for sell positions"""
        sl_levels = self.get_stop_loss_levels()
        if sl_levels['stoploss_up'] is not None:
            return sl_levels['stoploss_up'] + (10 * 0.0001)  # Add 10 points buffer
        return None
    
    def get_stop_loss_price_down(self) -> Optional[float]:
        """Get stop loss price for buy positions"""
        sl_levels = self.get_stop_loss_levels()
        if sl_levels['stoploss_down'] is not None:
            return sl_levels['stoploss_down'] - (10 * 0.0001)  # Subtract 10 points buffer
        return None
    
    def get_big_upper_wick_buffer(self) -> Optional[float]:
        """Get fresh upper wick level"""
        wick_levels = self.get_fresh_wick_levels()
        return wick_levels.get('upper_wick')
    
    def get_big_lower_wick_buffer(self) -> Optional[float]:
        """Get fresh lower wick level"""
        wick_levels = self.get_fresh_wick_levels()
        return wick_levels.get('lower_wick')
    
    def print_summary(self):
        """Print summary of all indicator values"""
        if self.df_processed is None:
            print("No data processed yet")
            return
            
        print("\n=== INDICATOR PROCESSOR SUMMARY ===")
        
        # Session info
        session_info = self.get_current_session_info()
        print(f"\nCurrent Session: {session_info.get('session_name', 'Unknown')}")
        print(f"Trading Allowed: {'Yes' if session_info.get('trade_allowed', False) else 'No'}")
        
        # Trend info
        trend_info = self.get_trend_info()
        print(f"\nTrend Information:")
        print(f"  SuperTrend: {trend_info['supertrend']['direction']} "
              f"at {trend_info['supertrend']['level']:.5f}")
        print(f"  Trend Detector: {trend_info['trend_detector']['name']}")
        
        # Levels
        print(f"\nSupport/Resistance Levels:")
        print(f"  Min Resistance: {self.current_levels['min_resistance']}")
        print(f"  Max Resistance: {self.current_levels['max_resistance']}")
        print(f"  Max Support: {self.current_levels['max_support']}")
        print(f"  Min Support: {self.current_levels['min_support']}")
        
        # Trading range
        if self.current_levels['in_significant_range']:
            range_pips = self.calculate_pip_difference(
                self.current_levels['current_level_max'],
                self.current_levels['current_level_min']
            )
            print(f"\nTrading Range: {range_pips:.1f} pips")
            print(f"  From: {self.current_levels['current_level_min']:.5f}")
            print(f"  To: {self.current_levels['current_level_max']:.5f}")
        else:
            print(f"\nNo significant trading range")
        
        # Fresh wicks
        wick_levels = self.get_fresh_wick_levels()
        print(f"\nFresh Wick Levels:")
        print(f"  Upper: {wick_levels['upper_wick']}")
        print(f"  Lower: {wick_levels['lower_wick']}")
        
        # Stop loss levels
        sl_levels = self.get_stop_loss_levels()
        print(f"\nStop Loss Levels:")
        print(f"  For Sells: {sl_levels['stoploss_up']}")
        print(f"  For Buys: {sl_levels['stoploss_down']}")


# Example usage
if __name__ == "__main__":
    from .trading_system_core import create_sample_dataframe
    
    # Create configuration
    config = TradingConfig(
        print_market_sessions=True,
        print_trend_direction=True,
        print_candle_indicator=True,
        print_level_id=True,
        print_sr_cycle=True
    )
    
    # Create sample data
    df = create_sample_dataframe(days=5)
    
    # Create processor
    processor = IndicatorProcessor(config)
    
    # Process all indicators
    df_processed = processor.process_all_indicators(df)
    
    # Print summary
    processor.print_summary()
    
    # Show recent processed data
    print("\n\nRecent processed data columns:")
    print(df_processed.columns.tolist())
    
    print("\nLast 5 rows sample:")
    print(df_processed[['close', 'session_name', 'trend_name', 
                       'is_bullish', 'has_top_wick', 'in_range']].tail(5))
