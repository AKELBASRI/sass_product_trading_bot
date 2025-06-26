# detect_range.py
"""
Range Detection Indicator
Converted from detect_range.mq5
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List, Tuple


class RangeDetector:
    """
    Detects price ranges (consolidation areas)
    """
    
    def __init__(self, min_candles_in_range: int = 3):
        """
        Initialize the range detector
        
        Args:
            min_candles_in_range: Minimum number of candles to confirm a range
        """
        self.min_candles = min_candles_in_range
        
        # Current range information
        self.range_high: Optional[float] = None
        self.range_low: Optional[float] = None
        self.range_start_time: Optional[datetime] = None
        self.range_end_time: Optional[datetime] = None
        self.range_start_index: Optional[int] = None
        self.range_active = False
        self.count_in_range = 0
        
    def _is_in_range(self, high: float, low: float, range_high: float, range_low: float) -> bool:
        """Check if a candle is within the range"""
        return high <= range_high and low >= range_low
    
    def _detect_range_start(self, df: pd.DataFrame, index: int) -> bool:
        """Try to detect the start of a new range"""
        if index + self.min_candles > len(df):
            return False
            
        # Use current candle as potential range boundaries
        potential_high = df.iloc[index]['high']
        potential_low = df.iloc[index]['low']
        
        # Check if next candles stay within range
        consecutive_in_range = 1
        
        for j in range(index + 1, min(index + self.min_candles, len(df))):
            if self._is_in_range(df.iloc[j]['high'], df.iloc[j]['low'], 
                               potential_high, potential_low):
                consecutive_in_range += 1
            else:
                break
                
        # If enough consecutive candles in range, we have a valid range
        return consecutive_in_range >= self.min_candles
    
    def calculate(self, df: pd.DataFrame, lookback_bars: int = 100) -> pd.DataFrame:
        """
        Calculate ranges for the dataframe
        
        Adds columns:
        - range_high: Current range high
        - range_low: Current range low
        - in_range: Boolean indicating if price is in a range
        - range_count: Number of bars in current range
        """
        # Create a copy to avoid modifying the original
        result_df = df.copy()
        
        # Initialize columns
        result_df['range_high'] = np.nan
        result_df['range_low'] = np.nan
        result_df['in_range'] = False
        result_df['range_count'] = 0
        
        # Reset state
        self.range_active = False
        self.count_in_range = 0
        
        # Process bars (limit lookback for performance)
        start_index = max(0, len(df) - lookback_bars)
        
        for i in range(start_index, len(df)):
            current = df.iloc[i]
            
            if not self.range_active:
                # Try to detect new range
                if i <= len(df) - self.min_candles:
                    if self._detect_range_start(df, i):
                        # Initialize new range
                        self.range_high = current['high']
                        self.range_low = current['low']
                        self.range_start_time = df.index[i]
                        self.range_start_index = i
                        self.range_active = True
                        self.count_in_range = 1
                        
                        # Mark this bar as in range
                        result_df.loc[df.index[i], 'range_high'] = self.range_high
                        result_df.loc[df.index[i], 'range_low'] = self.range_low
                        result_df.loc[df.index[i], 'in_range'] = True
                        result_df.loc[df.index[i], 'range_count'] = self.count_in_range
                        
            else:
                # Check if current bar breaks the range
                if current['high'] > self.range_high or current['low'] < self.range_low:
                    # Range broken
                    self.range_active = False
                    self.count_in_range = 0
                    self.range_end_time = df.index[i-1] if i > 0 else df.index[i]
                    
                else:
                    # Still in range
                    self.count_in_range += 1
                    self.range_end_time = df.index[i]
                    
                    # Update range info
                    result_df.loc[df.index[i], 'range_high'] = self.range_high
                    result_df.loc[df.index[i], 'range_low'] = self.range_low
                    result_df.loc[df.index[i], 'in_range'] = True
                    result_df.loc[df.index[i], 'range_count'] = self.count_in_range
        
        return result_df
    
    def get_current_range(self) -> Dict[str, Optional[float]]:
        """Get current range information"""
        return {
            'high': self.range_high,
            'low': self.range_low,
            'start_time': self.range_start_time,
            'end_time': self.range_end_time,
            'active': self.range_active,
            'count': self.count_in_range,
            'range_size_pips': self._calculate_range_size_pips()
        }
    
    def _calculate_range_size_pips(self, pip_size: float = 0.0001) -> Optional[float]:
        """Calculate the size of the current range in pips"""
        if self.range_high is not None and self.range_low is not None:
            return (self.range_high - self.range_low) / pip_size
        return None
    
    def find_ranges(self, df: pd.DataFrame, min_duration: int = 5) -> List[Dict]:
        """
        Find all ranges in the dataframe
        
        Args:
            min_duration: Minimum number of candles for a valid range
            
        Returns:
            List of range dictionaries
        """
        if 'in_range' not in df.columns:
            df = self.calculate(df)
            
        ranges = []
        current_range = None
        
        for i in range(len(df)):
            if df.iloc[i]['in_range']:
                if current_range is None:
                    # Start new range
                    current_range = {
                        'start_index': i,
                        'start_time': df.index[i],
                        'high': df.iloc[i]['range_high'],
                        'low': df.iloc[i]['range_low']
                    }
                else:
                    # Update range end
                    current_range['end_index'] = i
                    current_range['end_time'] = df.index[i]
                    current_range['duration'] = i - current_range['start_index'] + 1
            else:
                if current_range is not None:
                    # Range ended
                    if current_range.get('duration', 1) >= min_duration:
                        current_range['size_pips'] = (
                            (current_range['high'] - current_range['low']) / 0.0001
                        )
                        ranges.append(current_range)
                    current_range = None
        
        # Check if last range is still active
        if current_range is not None and current_range.get('duration', 1) >= min_duration:
            current_range['size_pips'] = (
                (current_range['high'] - current_range['low']) / 0.0001
            )
            ranges.append(current_range)
            
        return ranges
    
    def print_range_summary(self, df: pd.DataFrame):
        """Print summary of ranges found"""
        ranges = self.find_ranges(df)
        
        print("\n=== Range Detection Summary ===")
        print(f"Total ranges found: {len(ranges)}")
        
        if ranges:
            avg_duration = sum(r['duration'] for r in ranges) / len(ranges)
            avg_size = sum(r['size_pips'] for r in ranges) / len(ranges)
            
            print(f"Average range duration: {avg_duration:.1f} candles")
            print(f"Average range size: {avg_size:.1f} pips")
            
            print("\nRecent Ranges:")
            for r in ranges[-5:]:  # Show last 5 ranges
                print(f"  {r['start_time']} to {r['end_time']}: "
                      f"{r['size_pips']:.1f} pips, {r['duration']} candles")
        
        # Current range status
        current = self.get_current_range()
        if current['active']:
            print(f"\nCurrent Active Range:")
            print(f"  High: {current['high']:.5f}")
            print(f"  Low: {current['low']:.5f}")
            print(f"  Size: {current['range_size_pips']:.1f} pips")
            print(f"  Duration: {current['count']} candles")
        else:
            print("\nNo active range currently")


# Example usage
if __name__ == "__main__":
    from trading_system_core import create_sample_dataframe
    
    # Create sample data
    df = create_sample_dataframe(days=5)
    
    # Create range detector
    detector = RangeDetector(min_candles_in_range=3)
    
    # Calculate ranges
    df_with_ranges = detector.calculate(df, lookback_bars=500)
    
    # Print summary
    detector.print_range_summary(df_with_ranges)
    
    # Show recent data
    print("\nRecent data with range info:")
    recent = df_with_ranges[['close', 'range_high', 'range_low', 'in_range', 'range_count']].tail(20)
    print(recent[recent['in_range'] | recent['in_range'].shift(1)])
    
    # Count range statistics
    total_bars = len(df_with_ranges)
    bars_in_range = df_with_ranges['in_range'].sum()
    print(f"\nRange Statistics:")
    print(f"Total bars: {total_bars}")
    print(f"Bars in range: {bars_in_range}")
    print(f"Percentage in range: {bars_in_range/total_bars*100:.1f}%")
