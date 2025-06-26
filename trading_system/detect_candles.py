# detect_candles.py
"""
Candle Pattern Detection Indicator
Converted from detect_candles.mq5
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


class CandlePatternDetector:
    """
    Detects various candle patterns including wicks, body sizes, and candle types
    """
    
    def __init__(self, body_to_wick_ratio: float = 0.5, 
                 minimum_wick_size_pips: float = 5.0,
                 large_wick_ratio: float = 2.0,
                 pip_size: float = 0.0001):
        """
        Initialize the candle pattern detector
        
        Args:
            body_to_wick_ratio: Ratio to determine significant wicks
            minimum_wick_size_pips: Minimum wick size in pips
            large_wick_ratio: Ratio to determine very large wicks
            pip_size: Size of one pip
        """
        self.body_to_wick_ratio = body_to_wick_ratio
        self.minimum_wick_size = minimum_wick_size_pips * pip_size
        self.large_wick_ratio = large_wick_ratio
        
    def detect_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect all candle patterns and add columns to dataframe
        """
        # Create a copy to avoid modifying the original
        result_df = df.copy()
        
        # Calculate basic candle metrics
        result_df['body_size'] = abs(result_df['close'] - result_df['open'])
        result_df['upper_wick'] = result_df['high'] - result_df[['open', 'close']].max(axis=1)
        result_df['lower_wick'] = result_df[['open', 'close']].min(axis=1) - result_df['low']
        
        # Previous candle body size for comparison
        result_df['prev_body_size'] = result_df['body_size'].shift(1)
        
        # Detect patterns
        result_df['is_bullish'] = result_df['close'] > result_df['open']
        result_df['is_bearish'] = result_df['close'] < result_df['open']
        
        # Wick patterns
        result_df['has_top_wick'] = (
            (result_df['upper_wick'] >= self.minimum_wick_size) & 
            (result_df['upper_wick'] > result_df['body_size'] * self.body_to_wick_ratio)
        )
        
        result_df['has_bottom_wick'] = (
            (result_df['lower_wick'] >= self.minimum_wick_size) & 
            (result_df['lower_wick'] > result_df['body_size'] * self.body_to_wick_ratio)
        )
        
        # Large wick patterns
        result_df['has_large_top_wick'] = (
            (result_df['upper_wick'] >= self.minimum_wick_size) & 
            (result_df['upper_wick'] > result_df['body_size'] * self.large_wick_ratio)
        )
        
        result_df['has_large_bottom_wick'] = (
            (result_df['lower_wick'] >= self.minimum_wick_size) & 
            (result_df['lower_wick'] > result_df['body_size'] * self.large_wick_ratio)
        )
        
        # No wick patterns (very small wicks, less than 0.4 pips)
        result_df['no_top_wick'] = result_df['upper_wick'] <= 0.4 * 0.0001
        result_df['no_bottom_wick'] = result_df['lower_wick'] <= 0.4 * 0.0001
        
        # Body size comparison
        result_df['body_bigger_than_previous'] = (
            result_df['body_size'] > result_df['prev_body_size']
        ).fillna(False)
        
        result_df['body_smaller_than_previous'] = (
            result_df['body_size'] < result_df['prev_body_size']
        ).fillna(False)
        
        # Healthy candle (has both wicks but neither is too large)
        result_df['is_healthy_candle'] = (
            ~result_df['has_top_wick'] & 
            ~result_df['has_bottom_wick'] & 
            ~result_df['no_top_wick'] & 
            ~result_df['no_bottom_wick']
        )
        
        # Dominant wick (only show the larger wick if both exist)
        result_df['dominant_wick'] = 'none'
        
        # Set dominant wick
        mask_both_wicks = result_df['has_top_wick'] & result_df['has_bottom_wick']
        mask_top_larger = result_df['upper_wick'] > result_df['lower_wick']
        
        result_df.loc[result_df['has_top_wick'] & ~result_df['has_bottom_wick'], 'dominant_wick'] = 'top'
        result_df.loc[~result_df['has_top_wick'] & result_df['has_bottom_wick'], 'dominant_wick'] = 'bottom'
        result_df.loc[mask_both_wicks & mask_top_larger, 'dominant_wick'] = 'top'
        result_df.loc[mask_both_wicks & ~mask_top_larger, 'dominant_wick'] = 'bottom'
        
        return result_df
    
    def get_pattern_summary(self, df: pd.DataFrame, index: int) -> Dict[str, bool]:
        """
        Get a summary of patterns for a specific candle
        """
        if index < 0 or index >= len(df):
            return {}
            
        row = df.iloc[index]
        
        return {
            'is_bullish': bool(row.get('is_bullish', False)),
            'is_bearish': bool(row.get('is_bearish', False)),
            'has_top_wick': bool(row.get('has_top_wick', False)),
            'has_bottom_wick': bool(row.get('has_bottom_wick', False)),
            'has_large_top_wick': bool(row.get('has_large_top_wick', False)),
            'has_large_bottom_wick': bool(row.get('has_large_bottom_wick', False)),
            'no_top_wick': bool(row.get('no_top_wick', False)),
            'no_bottom_wick': bool(row.get('no_bottom_wick', False)),
            'body_bigger': bool(row.get('body_bigger_than_previous', False)),
            'body_smaller': bool(row.get('body_smaller_than_previous', False)),
            'is_healthy': bool(row.get('is_healthy_candle', False)),
            'dominant_wick': row.get('dominant_wick', 'none')
        }
    
    def find_exhaustion_candles(self, df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
        """
        Find potential exhaustion candles (large wicks at highs/lows)
        """
        if len(df) < lookback:
            return pd.DataFrame()
            
        # Calculate rolling high/low
        df['rolling_high'] = df['high'].rolling(window=lookback).max()
        df['rolling_low'] = df['low'].rolling(window=lookback).min()
        
        # Top exhaustion: Large top wick at rolling high
        df['top_exhaustion'] = (
            df['has_large_top_wick'] & 
            (df['high'] >= df['rolling_high'].shift(1))
        )
        
        # Bottom exhaustion: Large bottom wick at rolling low  
        df['bottom_exhaustion'] = (
            df['has_large_bottom_wick'] & 
            (df['low'] <= df['rolling_low'].shift(1))
        )
        
        return df
    
    def print_candle_info(self, df: pd.DataFrame, index: int):
        """Print detailed information about a specific candle"""
        if index < 0 or index >= len(df):
            print(f"Invalid index: {index}")
            return
            
        row = df.iloc[index]
        patterns = self.get_pattern_summary(df, index)
        
        print(f"\nCandle at {df.index[index]}:")
        print(f"  OHLC: O={row['open']:.5f}, H={row['high']:.5f}, "
              f"L={row['low']:.5f}, C={row['close']:.5f}")
        print(f"  Body Size: {row.get('body_size', 0):.5f}")
        print(f"  Upper Wick: {row.get('upper_wick', 0):.5f}")
        print(f"  Lower Wick: {row.get('lower_wick', 0):.5f}")
        print(f"  Type: {'Bullish' if patterns['is_bullish'] else 'Bearish'}")
        
        # Print active patterns
        active_patterns = []
        if patterns['has_top_wick']:
            active_patterns.append("Top Wick")
        if patterns['has_bottom_wick']:
            active_patterns.append("Bottom Wick")
        if patterns['has_large_top_wick']:
            active_patterns.append("Large Top Wick")
        if patterns['has_large_bottom_wick']:
            active_patterns.append("Large Bottom Wick")
        if patterns['no_top_wick']:
            active_patterns.append("No Top Wick")
        if patterns['no_bottom_wick']:
            active_patterns.append("No Bottom Wick")
        if patterns['is_healthy']:
            active_patterns.append("Healthy Candle")
        if patterns['body_bigger']:
            active_patterns.append("Body Bigger Than Previous")
        if patterns['body_smaller']:
            active_patterns.append("Body Smaller Than Previous")
            
        print(f"  Patterns: {', '.join(active_patterns) if active_patterns else 'None'}")
        print(f"  Dominant Wick: {patterns['dominant_wick']}")


# Example usage
if __name__ == "__main__":
    from trading_system_core import create_sample_dataframe
    
    # Create sample data
    df = create_sample_dataframe(days=2)
    
    # Create detector
    detector = CandlePatternDetector(
        body_to_wick_ratio=0.5,
        minimum_wick_size_pips=5.0,
        large_wick_ratio=2.0
    )
    
    # Detect patterns
    df_with_patterns = detector.detect_patterns(df)
    
    # Find exhaustion candles
    df_with_patterns = detector.find_exhaustion_candles(df_with_patterns)
    
    # Show recent candles with significant patterns
    print("Recent candles with significant wicks:")
    significant = df_with_patterns[
        df_with_patterns['has_top_wick'] | 
        df_with_patterns['has_bottom_wick'] |
        df_with_patterns['has_large_top_wick'] |
        df_with_patterns['has_large_bottom_wick']
    ].tail(10)
    
    if not significant.empty:
        for idx in significant.index:
            detector.print_candle_info(df_with_patterns, df_with_patterns.index.get_loc(idx))
    else:
        print("No candles with significant wicks found")
    
    # Summary statistics
    print("\n" + "="*50)
    print("Pattern Statistics:")
    print(f"Bullish candles: {df_with_patterns['is_bullish'].sum()}")
    print(f"Bearish candles: {df_with_patterns['is_bearish'].sum()}")
    print(f"Candles with top wick: {df_with_patterns['has_top_wick'].sum()}")
    print(f"Candles with bottom wick: {df_with_patterns['has_bottom_wick'].sum()}")
    print(f"Healthy candles: {df_with_patterns['is_healthy_candle'].sum()}")
    print(f"Top exhaustion candles: {df_with_patterns['top_exhaustion'].sum()}")
    print(f"Bottom exhaustion candles: {df_with_patterns['bottom_exhaustion'].sum()}")
