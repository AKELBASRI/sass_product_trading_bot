# fresh_wicks.py
"""
Fresh Wicks Indicator
Converted from fresh_wicks.mq5
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple


class FreshWicksIndicator:
    """
    Identifies significant candle wicks that haven't been tested by price
    """
    
    def __init__(self, min_wick_size_atr: float = 0.3, atr_period: int = 20):
        """
        Initialize the fresh wicks indicator
        
        Args:
            min_wick_size_atr: Minimum wick size as multiple of ATR
            atr_period: Period for ATR calculation
        """
        self.min_wick_size_atr = min_wick_size_atr
        self.atr_period = atr_period
        
        # Storage for current fresh wick levels
        self.latest_upper_wick: Optional[float] = None
        self.latest_lower_wick: Optional[float] = None
        self.latest_upper_wick_index: Optional[int] = None
        self.latest_lower_wick_index: Optional[int] = None
        
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=self.atr_period).mean()
        
        return atr
    
    def _is_fresh_level(self, df: pd.DataFrame, candle_index: int, level: float, 
                       is_upper_wick: bool, current_index: int) -> bool:
        """
        Check if a wick level is still fresh (untested)
        
        Args:
            df: DataFrame with price data
            candle_index: Index where the wick was formed
            level: Price level of the wick
            is_upper_wick: True for upper wick, False for lower wick
            current_index: Current bar index
            
        Returns:
            True if the level is still fresh
        """
        # Check all bars after the wick formation up to current index
        for i in range(candle_index + 1, current_index + 1):
            if is_upper_wick:
                # For upper wick, check if any subsequent high touched or exceeded it
                if df.iloc[i]['high'] >= level:
                    return False
            else:
                # For lower wick, check if any subsequent low touched or went below it
                if df.iloc[i]['low'] <= level:
                    return False
                    
        return True
    
    def calculate(self, df: pd.DataFrame, wait_for_close: bool = True) -> pd.DataFrame:
        """
        Calculate fresh wick levels
        
        Args:
            df: DataFrame with OHLCV data
            wait_for_close: Whether to wait for candle close before marking
            
        Returns:
            DataFrame with additional columns:
            - atr: Average True Range
            - upper_wick_size: Size of upper wick
            - lower_wick_size: Size of lower wick
            - fresh_upper_wick: Level of fresh upper wick (if any)
            - fresh_lower_wick: Level of fresh lower wick (if any)
        """
        # Create a copy to avoid modifying the original
        result_df = df.copy()
        
        # Calculate ATR
        result_df['atr'] = self.calculate_atr(df)
        
        # Calculate wick sizes
        result_df['upper_wick_size'] = (
            result_df['high'] - result_df[['open', 'close']].max(axis=1)
        )
        result_df['lower_wick_size'] = (
            result_df[['open', 'close']].min(axis=1) - result_df['low']
        )
        
        # Initialize fresh wick columns
        result_df['fresh_upper_wick'] = 0.0
        result_df['fresh_lower_wick'] = 0.0
        
        # Skip current candle if wait_for_close is True
        start_index = 1 if wait_for_close else 0
        
        # Process each bar
        for current_idx in range(self.atr_period, len(df)):
            current_atr = result_df.iloc[current_idx]['atr']
            
            # Reset latest wick tracking
            self.latest_upper_wick = None
            self.latest_lower_wick = None
            self.latest_upper_wick_index = None
            self.latest_lower_wick_index = None
            
            # Search for significant fresh wicks
            search_start = max(start_index, current_idx - 100)  # Limit search to last 100 bars
            
            for i in range(search_start, current_idx):
                # Skip if ATR not available
                if pd.isna(result_df.iloc[i]['atr']):
                    continue
                    
                wick_atr = result_df.iloc[i]['atr']
                
                # Check for significant upper wick
                upper_wick = result_df.iloc[i]['upper_wick_size']
                if upper_wick > wick_atr * self.min_wick_size_atr:
                    wick_level = df.iloc[i]['high']
                    if self._is_fresh_level(df, i, wick_level, True, current_idx):
                        # Update if this is more recent than current latest
                        if (self.latest_upper_wick_index is None or 
                            i > self.latest_upper_wick_index):
                            self.latest_upper_wick = wick_level
                            self.latest_upper_wick_index = i
                
                # Check for significant lower wick
                lower_wick = result_df.iloc[i]['lower_wick_size']
                if lower_wick > wick_atr * self.min_wick_size_atr:
                    wick_level = df.iloc[i]['low']
                    if self._is_fresh_level(df, i, wick_level, False, current_idx):
                        # Update if this is more recent than current latest
                        if (self.latest_lower_wick_index is None or 
                            i > self.latest_lower_wick_index):
                            self.latest_lower_wick = wick_level
                            self.latest_lower_wick_index = i
            
            # Set the fresh wick levels for current bar
            if self.latest_upper_wick is not None:
                result_df.loc[df.index[current_idx], 'fresh_upper_wick'] = self.latest_upper_wick
            if self.latest_lower_wick is not None:
                result_df.loc[df.index[current_idx], 'fresh_lower_wick'] = self.latest_lower_wick
        
        return result_df
    
    def get_current_fresh_wicks(self, df: pd.DataFrame) -> Dict[str, Optional[float]]:
        """Get the current fresh wick levels"""
        if 'fresh_upper_wick' not in df.columns:
            df = self.calculate(df)
            
        last_row = df.iloc[-1]
        
        return {
            'upper_wick': last_row['fresh_upper_wick'] if last_row['fresh_upper_wick'] != 0 else None,
            'lower_wick': last_row['fresh_lower_wick'] if last_row['fresh_lower_wick'] != 0 else None
        }
    
    def find_all_fresh_wicks(self, df: pd.DataFrame) -> Dict[str, List[Dict]]:
        """Find all current fresh wicks in the dataframe"""
        if 'atr' not in df.columns:
            df = self.calculate(df)
            
        fresh_upper_wicks = []
        fresh_lower_wicks = []
        
        # Check each candle for fresh wicks
        for i in range(self.atr_period, len(df) - 1):
            current_atr = df.iloc[i]['atr']
            
            # Check upper wick
            upper_wick = df.iloc[i]['upper_wick_size']
            if upper_wick > current_atr * self.min_wick_size_atr:
                wick_level = df.iloc[i]['high']
                if self._is_fresh_level(df, i, wick_level, True, len(df) - 1):
                    fresh_upper_wicks.append({
                        'index': i,
                        'time': df.index[i],
                        'level': wick_level,
                        'wick_size': upper_wick,
                        'atr_multiple': upper_wick / current_atr
                    })
            
            # Check lower wick
            lower_wick = df.iloc[i]['lower_wick_size']
            if lower_wick > current_atr * self.min_wick_size_atr:
                wick_level = df.iloc[i]['low']
                if self._is_fresh_level(df, i, wick_level, False, len(df) - 1):
                    fresh_lower_wicks.append({
                        'index': i,
                        'time': df.index[i],
                        'level': wick_level,
                        'wick_size': lower_wick,
                        'atr_multiple': lower_wick / current_atr
                    })
        
        return {
            'upper_wicks': fresh_upper_wicks,
            'lower_wicks': fresh_lower_wicks
        }
    
    def print_fresh_wick_summary(self, df: pd.DataFrame):
        """Print summary of fresh wicks"""
        all_wicks = self.find_all_fresh_wicks(df)
        current_wicks = self.get_current_fresh_wicks(df)
        
        print("\n=== Fresh Wicks Summary ===")
        print(f"Total fresh upper wicks: {len(all_wicks['upper_wicks'])}")
        print(f"Total fresh lower wicks: {len(all_wicks['lower_wicks'])}")
        
        if current_wicks['upper_wick']:
            print(f"\nCurrent fresh upper wick: {current_wicks['upper_wick']:.5f}")
        else:
            print("\nNo current fresh upper wick")
            
        if current_wicks['lower_wick']:
            print(f"Current fresh lower wick: {current_wicks['lower_wick']:.5f}")
        else:
            print("No current fresh lower wick")
        
        # Show recent fresh wicks
        if all_wicks['upper_wicks']:
            print("\nRecent fresh upper wicks:")
            for wick in all_wicks['upper_wicks'][-3:]:
                print(f"  {wick['time']}: {wick['level']:.5f} "
                      f"(size: {wick['wick_size']:.5f}, "
                      f"{wick['atr_multiple']:.2f}x ATR)")
        
        if all_wicks['lower_wicks']:
            print("\nRecent fresh lower wicks:")
            for wick in all_wicks['lower_wicks'][-3:]:
                print(f"  {wick['time']}: {wick['level']:.5f} "
                      f"(size: {wick['wick_size']:.5f}, "
                      f"{wick['atr_multiple']:.2f}x ATR)")


# Example usage
if __name__ == "__main__":
    from trading_system_core import create_sample_dataframe
    
    # Create sample data with more volatility for wicks
    np.random.seed(42)
    df = create_sample_dataframe(days=10)
    
    # Add some artificial wicks for testing
    for i in range(10, len(df), 20):
        # Create upper wick
        df.loc[df.index[i], 'high'] = df.iloc[i]['high'] + 0.0015
        # Create lower wick
        df.loc[df.index[i+5], 'low'] = df.iloc[i+5]['low'] - 0.0015
    
    # Create indicator
    fresh_wicks = FreshWicksIndicator(min_wick_size_atr=0.3, atr_period=20)
    
    # Calculate fresh wicks
    df_with_wicks = fresh_wicks.calculate(df)
    
    # Print summary
    fresh_wicks.print_fresh_wick_summary(df_with_wicks)
    
    # Show recent data with fresh wick levels
    print("\nRecent data with fresh wick levels:")
    recent = df_with_wicks[['close', 'fresh_upper_wick', 'fresh_lower_wick']].tail(10)
    print(recent[
        (recent['fresh_upper_wick'] != 0) | 
        (recent['fresh_lower_wick'] != 0)
    ])
