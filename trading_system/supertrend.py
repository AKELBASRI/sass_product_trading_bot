# supertrend.py
"""
SuperTrend Indicator
Converted from SuperTrend.mq5
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional


class SuperTrend:
    """
    SuperTrend indicator implementation
    """
    
    def __init__(self, period: int = 10, multiplier: float = 3.0):
        """
        Initialize SuperTrend indicator
        
        Args:
            period: ATR period for calculation
            multiplier: ATR multiplier for bands
        """
        self.period = period
        self.multiplier = multiplier
        
    def calculate_atr(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate Average True Range
        """
        # Calculate True Range
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Calculate ATR as moving average of True Range
        atr = true_range.rolling(window=self.period).mean()
        
        return atr
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate SuperTrend indicator
        
        Returns DataFrame with additional columns:
        - atr: Average True Range
        - basic_upper: Basic upper band
        - basic_lower: Basic lower band
        - final_upper: Final upper band
        - final_lower: Final lower band
        - supertrend: SuperTrend line
        - trend: Trend direction (1 for uptrend, -1 for downtrend)
        - trend_changed: Boolean indicating trend change
        """
        # Create a copy to avoid modifying the original
        result_df = df.copy()
        
        # Calculate ATR
        result_df['atr'] = self.calculate_atr(df)
        
        # Calculate basic bands
        hl_avg = (df['high'] + df['low']) / 2
        result_df['basic_upper'] = hl_avg + (self.multiplier * result_df['atr'])
        result_df['basic_lower'] = hl_avg - (self.multiplier * result_df['atr'])
        
        # Initialize final bands
        result_df['final_upper'] = result_df['basic_upper']
        result_df['final_lower'] = result_df['basic_lower']
        
        # Initialize trend
        result_df['trend'] = 1
        
        # Calculate SuperTrend
        for i in range(1, len(result_df)):
            # Current values
            curr_close = result_df.iloc[i]['close']
            
            # Previous values
            prev_close = result_df.iloc[i-1]['close']
            prev_trend = result_df.iloc[i-1]['trend']
            prev_final_upper = result_df.iloc[i-1]['final_upper']
            prev_final_lower = result_df.iloc[i-1]['final_lower']
            
            # Current basic bands
            curr_basic_upper = result_df.iloc[i]['basic_upper']
            curr_basic_lower = result_df.iloc[i]['basic_lower']
            
            # Calculate final bands
            # Upper band
            if curr_basic_upper < prev_final_upper or prev_close > prev_final_upper:
                final_upper = curr_basic_upper
            else:
                final_upper = prev_final_upper
                
            # Lower band
            if curr_basic_lower > prev_final_lower or prev_close < prev_final_lower:
                final_lower = curr_basic_lower
            else:
                final_lower = prev_final_lower
            
            result_df.loc[result_df.index[i], 'final_upper'] = final_upper
            result_df.loc[result_df.index[i], 'final_lower'] = final_lower
            
            # Determine trend
            if prev_trend == 1:  # Previous uptrend
                if curr_close <= final_lower:
                    trend = -1
                else:
                    trend = 1
            else:  # Previous downtrend
                if curr_close >= final_upper:
                    trend = 1
                else:
                    trend = -1
                    
            result_df.loc[result_df.index[i], 'trend'] = trend
        
        # Set SuperTrend line based on trend
        result_df['supertrend'] = np.where(
            result_df['trend'] == 1,
            result_df['final_lower'],
            result_df['final_upper']
        )
        
        # Identify trend changes
        result_df['trend_changed'] = result_df['trend'] != result_df['trend'].shift(1)
        
        return result_df
    
    def get_current_trend(self, df: pd.DataFrame) -> int:
        """
        Get the current trend direction
        Returns: 1 for uptrend, -1 for downtrend
        """
        if 'trend' not in df.columns:
            df = self.calculate(df)
        
        return int(df['trend'].iloc[-1])
    
    def get_trend_info(self, df: pd.DataFrame, index: int = -1) -> dict:
        """
        Get detailed trend information for a specific bar
        """
        if 'trend' not in df.columns:
            df = self.calculate(df)
            
        row = df.iloc[index]
        
        return {
            'trend': int(row['trend']),
            'trend_name': 'Uptrend' if row['trend'] == 1 else 'Downtrend',
            'supertrend_level': float(row['supertrend']),
            'atr': float(row['atr']),
            'upper_band': float(row['final_upper']),
            'lower_band': float(row['final_lower']),
            'trend_changed': bool(row['trend_changed'])
        }
    
    def find_trend_changes(self, df: pd.DataFrame, lookback: int = 50) -> pd.DataFrame:
        """
        Find recent trend changes
        """
        if 'trend' not in df.columns:
            df = self.calculate(df)
            
        # Get trend changes in the lookback period
        recent_changes = df[df['trend_changed']].tail(lookback)
        
        return recent_changes
    
    def print_current_status(self, df: pd.DataFrame):
        """Print current SuperTrend status"""
        info = self.get_trend_info(df)
        
        print("\n=== SuperTrend Status ===")
        print(f"Current Trend: {info['trend_name']} ({info['trend']})")
        print(f"SuperTrend Level: {info['supertrend_level']:.5f}")
        print(f"Upper Band: {info['upper_band']:.5f}")
        print(f"Lower Band: {info['lower_band']:.5f}")
        print(f"ATR: {info['atr']:.5f}")
        print(f"Trend Changed: {'Yes' if info['trend_changed'] else 'No'}")
        
        # Find last trend change
        changes = self.find_trend_changes(df)
        if not changes.empty:
            last_change = changes.iloc[-1]
            print(f"\nLast Trend Change: {last_change.name}")
            print(f"  From: {'Downtrend' if info['trend'] == 1 else 'Uptrend'}")
            print(f"  To: {info['trend_name']}")


# Example usage
if __name__ == "__main__":
    from trading_system_core import create_sample_dataframe
    
    # Create sample data
    df = create_sample_dataframe(days=10)
    
    # Create SuperTrend indicator
    supertrend = SuperTrend(period=10, multiplier=3.0)
    
    # Calculate indicator
    df_with_st = supertrend.calculate(df)
    
    # Print current status
    supertrend.print_current_status(df_with_st)
    
    # Show recent data
    print("\nRecent SuperTrend data:")
    print(df_with_st[['close', 'supertrend', 'trend', 'trend_changed']].tail(10))
    
    # Find and show trend changes
    print("\nRecent trend changes:")
    changes = supertrend.find_trend_changes(df_with_st)
    for idx, row in changes.iterrows():
        prev_trend = -row['trend']  # Opposite of current trend
        print(f"{idx}: {'Downtrend' if prev_trend == -1 else 'Uptrend'} "
              f"-> {'Uptrend' if row['trend'] == 1 else 'Downtrend'}")
