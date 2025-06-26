# level_identification.py
"""
Support/Resistance Level Identification Indicator
Converted from LevelIdentification.mq5
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class PriceLevel:
    """Represents a support or resistance level"""
    level: float
    level_type: str  # 'resistance' or 'support'
    creation_time: datetime
    creation_index: int
    is_broken: bool = False
    break_time: Optional[datetime] = None


class LevelIdentification:
    """
    Identifies support and resistance levels based on candle patterns
    """
    
    def __init__(self, min_pips: float = 0.0, pip_size: float = 0.0001):
        """
        Initialize the level identification indicator
        
        Args:
            min_pips: Minimum distance in pips between important levels
            pip_size: Size of one pip
        """
        self.min_pips = min_pips
        self.pip_size = pip_size
        self.min_distance = min_pips * pip_size
        
        # Storage for levels
        self.resistance_levels: List[PriceLevel] = []
        self.support_levels: List[PriceLevel] = []
        
        # Current min/max levels
        self.min_resistance: Optional[float] = None
        self.max_resistance: Optional[float] = None
        self.min_support: Optional[float] = None
        self.max_support: Optional[float] = None
    
    def _calculate_pip_difference(self, price1: float, price2: float) -> float:
        """Calculate pip difference between two price levels"""
        return abs(price1 - price2) / self.pip_size
    
    def _identify_new_levels(self, df: pd.DataFrame, index: int):
        """Identify new support/resistance levels from candle patterns"""
        if index < 1 or index >= len(df):
            return
            
        # Get current and previous candle data
        curr = df.iloc[index]
        prev = df.iloc[index - 1]
        
        # Check for resistance: bullish candle followed by bearish candle
        if prev['close'] > prev['open'] and curr['close'] < curr['open']:
            # Resistance level at the open of the current candle
            level = PriceLevel(
                level=curr['open'],
                level_type='resistance',
                creation_time=df.index[index],
                creation_index=index
            )
            self.resistance_levels.append(level)
        
        # Check for support: bearish candle followed by bullish candle
        if prev['close'] < prev['open'] and curr['close'] > curr['open']:
            # Support level at the open of the current candle
            level = PriceLevel(
                level=curr['open'],
                level_type='support',
                creation_time=df.index[index],
                creation_index=index
            )
            self.support_levels.append(level)
    
    def _check_level_breaks(self, df: pd.DataFrame, current_index: int):
        """Check if any levels have been broken"""
        if current_index < 0 or current_index >= len(df):
            return
            
        current_close = df.iloc[current_index]['close']
        current_time = df.index[current_index]
        
        # Check resistance levels
        for level in self.resistance_levels:
            if not level.is_broken and level.creation_index < current_index:
                # Check if close is above resistance (with small buffer)
                if current_close > level.level + (5 * self.pip_size * 0.1):
                    level.is_broken = True
                    level.break_time = current_time
        
        # Check support levels
        for level in self.support_levels:
            if not level.is_broken and level.creation_index < current_index:
                # Check if close is below support (with small buffer)
                if current_close < level.level - (5 * self.pip_size * 0.1):
                    level.is_broken = True
                    level.break_time = current_time
    
    def _clean_broken_levels(self):
        """Remove broken levels from the lists"""
        self.resistance_levels = [l for l in self.resistance_levels if not l.is_broken]
        self.support_levels = [l for l in self.support_levels if not l.is_broken]
    
    def _find_min_max_levels(self):
        """Find min/max resistance and support levels with minimum pip distance"""
        # Reset min/max levels
        self.min_resistance = None
        self.max_resistance = None
        self.min_support = None
        self.max_support = None
        
        # Sort resistance levels (ascending)
        if len(self.resistance_levels) > 1:
            sorted_resistance = sorted([l.level for l in self.resistance_levels])
            
            # Find pair with minimum pip distance
            for i in range(len(sorted_resistance) - 1):
                pip_diff = self._calculate_pip_difference(
                    sorted_resistance[i+1], sorted_resistance[i]
                )
                if pip_diff > self.min_pips:
                    self.min_resistance = sorted_resistance[i]
                    self.max_resistance = sorted_resistance[i+1]
                    break
            
            # If no pair found, use min and max
            if self.min_resistance is None and len(sorted_resistance) >= 2:
                range_pips = self._calculate_pip_difference(
                    sorted_resistance[-1], sorted_resistance[0]
                )
                if range_pips > self.min_pips:
                    self.min_resistance = sorted_resistance[0]
                    self.max_resistance = sorted_resistance[-1]
        
        # Sort support levels (descending)
        if len(self.support_levels) > 1:
            sorted_support = sorted([l.level for l in self.support_levels], reverse=True)
            
            # Find pair with minimum pip distance
            for i in range(len(sorted_support) - 1):
                pip_diff = self._calculate_pip_difference(
                    sorted_support[i], sorted_support[i+1]
                )
                if pip_diff > self.min_pips:
                    self.max_support = sorted_support[i]
                    self.min_support = sorted_support[i+1]
                    break
            
            # If no pair found, use max and min
            if self.max_support is None and len(sorted_support) >= 2:
                range_pips = self._calculate_pip_difference(
                    sorted_support[0], sorted_support[-1]
                )
                if range_pips > self.min_pips:
                    self.max_support = sorted_support[0]
                    self.min_support = sorted_support[-1]
    
    def calculate(self, df: pd.DataFrame, max_bars: int = 1000) -> pd.DataFrame:
        """
        Calculate support and resistance levels for the dataframe
        """
        # Create a copy to avoid modifying the original
        result_df = df.copy()
        
        # Initialize columns
        result_df['resistance'] = np.nan
        result_df['support'] = np.nan
        result_df['min_resistance'] = np.nan
        result_df['max_resistance'] = np.nan
        result_df['min_support'] = np.nan
        result_df['max_support'] = np.nan
        
        # Clear existing levels
        self.resistance_levels = []
        self.support_levels = []
        
        # Process bars (limit to max_bars for performance)
        start_index = max(0, len(df) - max_bars)
        
        for i in range(start_index, len(df)):
            # Identify new levels
            self._identify_new_levels(df, i)
            
            # Check for level breaks
            self._check_level_breaks(df, i)
            
            # Clean broken levels
            self._clean_broken_levels()
            
            # Find min/max levels
            self._find_min_max_levels()
            
            # Mark current levels in the dataframe
            if i > 0:
                # Check if this bar created a new level
                prev = df.iloc[i-1]
                curr = df.iloc[i]
                
                # Resistance pattern
                if prev['close'] > prev['open'] and curr['close'] < curr['open']:
                    result_df.loc[df.index[i], 'resistance'] = curr['open']
                
                # Support pattern
                if prev['close'] < prev['open'] and curr['close'] > curr['open']:
                    result_df.loc[df.index[i], 'support'] = curr['open']
            
            # Set min/max levels
            if self.min_resistance is not None:
                result_df.loc[df.index[i], 'min_resistance'] = self.min_resistance
            if self.max_resistance is not None:
                result_df.loc[df.index[i], 'max_resistance'] = self.max_resistance
            if self.min_support is not None:
                result_df.loc[df.index[i], 'min_support'] = self.min_support
            if self.max_support is not None:
                result_df.loc[df.index[i], 'max_support'] = self.max_support
        
        return result_df
    
    def get_current_levels(self) -> Dict[str, Optional[float]]:
        """Get current min/max support and resistance levels"""
        return {
            'min_resistance': self.min_resistance,
            'max_resistance': self.max_resistance,
            'min_support': self.min_support,
            'max_support': self.max_support,
            'trading_range_pips': self._get_trading_range_pips()
        }
    
    def _get_trading_range_pips(self) -> Optional[float]:
        """Calculate the trading range between max support and min resistance"""
        if self.max_support is not None and self.min_resistance is not None:
            return self._calculate_pip_difference(self.min_resistance, self.max_support)
        return None
    
    def get_active_levels(self) -> Dict[str, List[float]]:
        """Get all active (unbroken) support and resistance levels"""
        return {
            'resistance': sorted([l.level for l in self.resistance_levels]),
            'support': sorted([l.level for l in self.support_levels], reverse=True)
        }
    
    def print_level_summary(self):
        """Print a summary of current levels"""
        print("\n=== Level Identification Summary ===")
        
        # Active levels
        active = self.get_active_levels()
        print(f"Active Resistance Levels: {len(active['resistance'])}")
        if active['resistance']:
            print(f"  Range: {active['resistance'][0]:.5f} to {active['resistance'][-1]:.5f}")
        
        print(f"Active Support Levels: {len(active['support'])}")
        if active['support']:
            print(f"  Range: {active['support'][0]:.5f} to {active['support'][-1]:.5f}")
        
        # Current min/max levels
        levels = self.get_current_levels()
        print("\nCurrent Min/Max Levels:")
        print(f"  Min Resistance: {levels['min_resistance']:.5f if levels['min_resistance'] else 'None'}")
        print(f"  Max Resistance: {levels['max_resistance']:.5f if levels['max_resistance'] else 'None'}")
        print(f"  Max Support: {levels['max_support']:.5f if levels['max_support'] else 'None'}")
        print(f"  Min Support: {levels['min_support']:.5f if levels['min_support'] else 'None'}")
        
        if levels['trading_range_pips']:
            print(f"\nTrading Range (Max Support to Min Resistance): {levels['trading_range_pips']:.1f} pips")


# Example usage
if __name__ == "__main__":
    from trading_system_core import create_sample_dataframe
    
    # Create sample data
    df = create_sample_dataframe(days=5)
    
    # Create indicator
    level_id = LevelIdentification(min_pips=10.0)
    
    # Calculate levels
    df_with_levels = level_id.calculate(df, max_bars=500)
    
    # Show recent level formations
    print("Recent Support/Resistance Formations:")
    recent_levels = df_with_levels[
        df_with_levels['resistance'].notna() | 
        df_with_levels['support'].notna()
    ].tail(10)
    
    for idx, row in recent_levels.iterrows():
        if pd.notna(row['resistance']):
            print(f"{idx}: Resistance at {row['resistance']:.5f}")
        if pd.notna(row['support']):
            print(f"{idx}: Support at {row['support']:.5f}")
    
    # Print summary
    level_id.print_level_summary()
    
    # Show current levels in the last few bars
    print("\nLast 5 bars with min/max levels:")
    print(df_with_levels[['close', 'min_resistance', 'max_resistance', 
                          'min_support', 'max_support']].tail(5))
