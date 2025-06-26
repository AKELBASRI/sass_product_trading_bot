# candle_retracement.py
"""
Candle Retracement Indicator
Based on wick retracement logic from the MQL5 system
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple


class CandleRetracementIndicator:
    """
    Identifies potential stop loss levels based on candle wick retracements
    """
    
    def __init__(self, min_retrace_percent: float = 30.0):
        """
        Initialize the candle retracement indicator
        
        Args:
            min_retrace_percent: Minimum retracement percentage
        """
        self.min_retrace_percent = min_retrace_percent
        
    def calculate_wick_retracement(self, open_price: float, close_price: float, 
                                  high: float, low: float, is_bullish: bool) -> Tuple[float, float]:
        """
        Calculate retracement levels for a candle
        
        Returns:
            Tuple of (upper_retracement, lower_retracement)
        """
        if is_bullish:
            # For bullish candles
            body_top = close_price
            body_bottom = open_price
            upper_wick = high - body_top
            lower_wick = body_bottom - low
            
            # Upper retracement (for sell stop loss)
            upper_retrace = body_top + (upper_wick * self.min_retrace_percent / 100)
            
            # Lower retracement (for buy stop loss)
            lower_retrace = body_bottom - (lower_wick * self.min_retrace_percent / 100)
            
        else:
            # For bearish candles
            body_top = open_price
            body_bottom = close_price
            upper_wick = high - body_top
            lower_wick = body_bottom - low
            
            # Upper retracement (for sell stop loss)
            upper_retrace = body_top + (upper_wick * self.min_retrace_percent / 100)
            
            # Lower retracement (for buy stop loss)
            lower_retrace = body_bottom - (lower_wick * self.min_retrace_percent / 100)
            
        return upper_retrace, lower_retrace
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate stop loss levels based on candle retracements
        
        Adds columns:
        - stoploss_up: Stop loss level for sell positions (above price)
        - stoploss_down: Stop loss level for buy positions (below price)
        - has_valid_sl_up: Boolean indicating valid upper stop loss
        - has_valid_sl_down: Boolean indicating valid lower stop loss
        """
        # Create a copy to avoid modifying the original
        result_df = df.copy()
        
        # Initialize columns
        result_df['stoploss_up'] = np.nan
        result_df['stoploss_down'] = np.nan
        result_df['has_valid_sl_up'] = False
        result_df['has_valid_sl_down'] = False
        
        # Calculate for each candle
        for i in range(len(df)):
            row = df.iloc[i]
            
            # Determine if bullish or bearish
            is_bullish = row['close'] > row['open']
            
            # Calculate retracement levels
            upper_retrace, lower_retrace = self.calculate_wick_retracement(
                row['open'], row['close'], row['high'], row['low'], is_bullish
            )
            
            # Validate upper stop loss (must have upper wick)
            upper_wick_size = row['high'] - max(row['open'], row['close'])
            if upper_wick_size > 0:
                result_df.loc[df.index[i], 'stoploss_up'] = upper_retrace
                result_df.loc[df.index[i], 'has_valid_sl_up'] = True
            
            # Validate lower stop loss (must have lower wick)
            lower_wick_size = min(row['open'], row['close']) - row['low']
            if lower_wick_size > 0:
                result_df.loc[df.index[i], 'stoploss_down'] = lower_retrace
                result_df.loc[df.index[i], 'has_valid_sl_down'] = True
        
        return result_df
    
    def get_current_stop_levels(self, df: pd.DataFrame) -> Dict[str, Optional[float]]:
        """Get current stop loss levels"""
        if 'stoploss_up' not in df.columns:
            df = self.calculate(df)
            
        last_row = df.iloc[-1]
        
        return {
            'stoploss_up': last_row['stoploss_up'] if pd.notna(last_row['stoploss_up']) else None,
            'stoploss_down': last_row['stoploss_down'] if pd.notna(last_row['stoploss_down']) else None,
            'has_valid_sl_up': bool(last_row['has_valid_sl_up']),
            'has_valid_sl_down': bool(last_row['has_valid_sl_down'])
        }
    
    def find_recent_stop_levels(self, df: pd.DataFrame, lookback: int = 10) -> pd.DataFrame:
        """Find recent valid stop loss levels"""
        if 'stoploss_up' not in df.columns:
            df = self.calculate(df)
            
        # Get recent candles with valid stop levels
        recent = df.tail(lookback)
        valid_stops = recent[recent['has_valid_sl_up'] | recent['has_valid_sl_down']]
        
        return valid_stops
    
    def print_stop_level_summary(self, df: pd.DataFrame):
        """Print summary of stop loss levels"""
        current = self.get_current_stop_levels(df)
        
        print("\n=== Candle Retracement Stop Levels ===")
        print(f"Retracement Percentage: {self.min_retrace_percent}%")
        
        print("\nCurrent Stop Levels:")
        if current['stoploss_up'] is not None:
            print(f"  Stop Loss Up (for sells): {current['stoploss_up']:.5f}")
        else:
            print("  Stop Loss Up: Not available")
            
        if current['stoploss_down'] is not None:
            print(f"  Stop Loss Down (for buys): {current['stoploss_down']:.5f}")
        else:
            print("  Stop Loss Down: Not available")
        
        # Show recent stop levels
        recent_stops = self.find_recent_stop_levels(df, lookback=20)
        
        if not recent_stops.empty:
            print("\nRecent Valid Stop Levels:")
            for idx, row in recent_stops.tail(5).iterrows():
                parts = []
                if row['has_valid_sl_up']:
                    parts.append(f"SL Up: {row['stoploss_up']:.5f}")
                if row['has_valid_sl_down']:
                    parts.append(f"SL Down: {row['stoploss_down']:.5f}")
                if parts:
                    print(f"  {idx}: {', '.join(parts)}")


# Example usage
if __name__ == "__main__":
    from trading_system_core import create_sample_dataframe
    
    # Create sample data
    df = create_sample_dataframe(days=2)
    
    # Create indicator
    retracement = CandleRetracementIndicator(min_retrace_percent=30.0)
    
    # Calculate stop levels
    df_with_stops = retracement.calculate(df)
    
    # Print summary
    retracement.print_stop_level_summary(df_with_stops)
    
    # Show recent data with stop levels
    print("\nRecent candles with stop levels:")
    recent = df_with_stops[['open', 'high', 'low', 'close', 
                           'stoploss_up', 'stoploss_down',
                           'has_valid_sl_up', 'has_valid_sl_down']].tail(10)
    
    print(recent[recent['has_valid_sl_up'] | recent['has_valid_sl_down']])
