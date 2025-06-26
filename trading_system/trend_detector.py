# trend_detector.py
"""
Trend Detector Indicator
Converted from trenddetector.mq5
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List


class TrendDetector:
    """
    Custom trend detection based on support/resistance breakouts
    """
    
    def __init__(self, max_bars_to_process: int = 1000):
        """
        Initialize the trend detector
        
        Args:
            max_bars_to_process: Maximum number of bars to process
        """
        self.max_bars = max_bars_to_process
        
        # Single support/resistance levels
        self.resistance_level: Optional[float] = None
        self.support_level: Optional[float] = None
        self.resistance_time: Optional[datetime] = None
        self.support_time: Optional[datetime] = None
        
    def _identify_levels(self, df: pd.DataFrame, index: int):
        """Identify support and resistance levels from candle patterns"""
        if index < 1 or index >= len(df):
            return
            
        # Get current and previous candle
        curr = df.iloc[index]
        prev = df.iloc[index - 1]
        
        # Identify resistance: bullish candle followed by bearish candle
        if prev['close'] > prev['open'] and curr['close'] < curr['open']:
            self.resistance_level = prev['open']  # Resistance at open of previous candle
            self.resistance_time = df.index[index]
            
        # Identify support: bearish candle followed by bullish candle
        if prev['close'] < prev['open'] and curr['close'] > curr['open']:
            self.support_level = prev['open']  # Support at open of previous candle
            self.support_time = df.index[index]
    
    def _check_breakouts(self, df: pd.DataFrame, index: int) -> int:
        """
        Check for support/resistance breakouts
        Returns: 1 for uptrend, -1 for downtrend, 0 for no trend
        """
        if index < 0 or index >= len(df):
            return 0
            
        current_close = df.iloc[index]['close']
        current_time = df.index[index]
        
        # Check resistance breakout (uptrend)
        if (self.resistance_level is not None and 
            self.resistance_time is not None and
            current_time > self.resistance_time and
            current_close > self.resistance_level):
            return 1
            
        # Check support breakout (downtrend)
        if (self.support_level is not None and
            self.support_time is not None and
            current_time > self.support_time and
            current_close < self.support_level):
            return -1
            
        return 0
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate trend direction for the dataframe
        
        Adds columns:
        - trend: 1 for uptrend, -1 for downtrend, 0 for no trend
        - trend_name: Human readable trend name
        """
        # Create a copy to avoid modifying the original
        result_df = df.copy()
        
        # Initialize columns
        result_df['trend'] = 0
        result_df['trend_name'] = 'No Trend'
        
        # Reset levels
        self.resistance_level = None
        self.support_level = None
        self.resistance_time = None
        self.support_time = None
        
        # Limit processing
        start_index = max(0, len(df) - self.max_bars)
        
        # Track current trend
        current_trend = 0
        
        for i in range(start_index, len(df)):
            # Identify new levels
            self._identify_levels(df, i)
            
            # Check for breakouts
            breakout_signal = self._check_breakouts(df, i)
            
            # Update trend if breakout detected, otherwise maintain previous trend
            if breakout_signal != 0:
                current_trend = breakout_signal
            
            # Set trend values
            result_df.loc[df.index[i], 'trend'] = current_trend
            
            # Set trend name
            if current_trend == 1:
                result_df.loc[df.index[i], 'trend_name'] = 'Uptrend'
            elif current_trend == -1:
                result_df.loc[df.index[i], 'trend_name'] = 'Downtrend'
            else:
                result_df.loc[df.index[i], 'trend_name'] = 'No Trend'
        
        return result_df
    
    def get_current_levels(self) -> Dict[str, Optional[float]]:
        """Get current support and resistance levels"""
        return {
            'resistance': self.resistance_level,
            'support': self.support_level,
            'resistance_time': self.resistance_time,
            'support_time': self.support_time
        }
    
    def get_current_trend(self, df: pd.DataFrame) -> Dict[str, any]:
        """Get current trend information"""
        if 'trend' not in df.columns:
            df = self.calculate(df)
            
        current_trend = df['trend'].iloc[-1]
        current_name = df['trend_name'].iloc[-1]
        
        return {
            'trend': int(current_trend),
            'trend_name': current_name,
            'resistance': self.resistance_level,
            'support': self.support_level
        }
    
    def find_trend_changes(self, df: pd.DataFrame, lookback: int = 50) -> List[Dict]:
        """Find recent trend changes"""
        if 'trend' not in df.columns:
            df = self.calculate(df)
            
        changes = []
        
        # Look for trend changes
        for i in range(max(1, len(df) - lookback), len(df)):
            curr_trend = df.iloc[i]['trend']
            prev_trend = df.iloc[i-1]['trend']
            
            if curr_trend != prev_trend and curr_trend != 0:
                changes.append({
                    'time': df.index[i],
                    'from_trend': int(prev_trend),
                    'to_trend': int(curr_trend),
                    'from_name': self._get_trend_name(prev_trend),
                    'to_name': self._get_trend_name(curr_trend),
                    'close': df.iloc[i]['close']
                })
                
        return changes
    
    def _get_trend_name(self, trend: int) -> str:
        """Convert trend value to name"""
        if trend == 1:
            return 'Uptrend'
        elif trend == -1:
            return 'Downtrend'
        else:
            return 'No Trend'
    
    def print_status(self, df: pd.DataFrame):
        """Print current trend status"""
        info = self.get_current_trend(df)
        levels = self.get_current_levels()
        
        print("\n=== Trend Detector Status ===")
        print(f"Current Trend: {info['trend_name']} ({info['trend']})")
        
        if levels['resistance'] is not None:
            print(f"Resistance Level: {levels['resistance']:.5f} "
                  f"(set at {levels['resistance_time']})")
        else:
            print("Resistance Level: Not set")
            
        if levels['support'] is not None:
            print(f"Support Level: {levels['support']:.5f} "
                  f"(set at {levels['support_time']})")
        else:
            print("Support Level: Not set")
        
        # Show recent trend changes
        changes = self.find_trend_changes(df, lookback=20)
        if changes:
            print("\nRecent Trend Changes:")
            for change in changes[-5:]:  # Show last 5 changes
                print(f"  {change['time']}: {change['from_name']} -> {change['to_name']} "
                      f"at {change['close']:.5f}")


# Example usage
if __name__ == "__main__":
    from trading_system_core import create_sample_dataframe
    
    # Create sample data
    df = create_sample_dataframe(days=10)
    
    # Create trend detector
    detector = TrendDetector(max_bars_to_process=1000)
    
    # Calculate trend
    df_with_trend = detector.calculate(df)
    
    # Print status
    detector.print_status(df_with_trend)
    
    # Show recent data
    print("\nRecent trend data:")
    print(df_with_trend[['close', 'trend', 'trend_name']].tail(10))
    
    # Count trend distribution
    print("\nTrend Distribution:")
    print(df_with_trend['trend_name'].value_counts())
