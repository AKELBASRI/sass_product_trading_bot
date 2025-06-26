# breakout_scenarios.py
"""
Breakout Trading Scenarios
Converted from BreakoutScenarios.mqh
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from datetime import datetime

from .trading_system_core import TradingConfig, CandleUtils, PriceUtils
from .indicator_processor import IndicatorProcessor
from .trade_manager import TradeManager


class BreakoutScenarios:
    """
    Manages breakout trading scenarios
    """
    
    def __init__(self, config: TradingConfig, trade_manager: TradeManager, 
                 indicator_processor: IndicatorProcessor):
        """
        Initialize breakout scenarios
        
        Args:
            config: Trading configuration
            trade_manager: Trade manager instance
            indicator_processor: Indicator processor instance
        """
        self.config = config
        self.trade_manager = trade_manager
        self.indicator_processor = indicator_processor
        
        # Track if trade was executed
        self.trade_executed_flag = False
        
    def check_break_and_close_sell(self, df: pd.DataFrame) -> bool:
        """
        Check for sell setup with focus on M30 support breach
        
        Returns:
            True if setup detected (not necessarily executed)
        """
        self.trade_executed_flag = False
        
        if df is None or len(df) < 2:
            return False
        
        # Get price data
        current_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        prev_high = df['high'].iloc[-2]
        prev_low = df['low'].iloc[-2]
        
        # Get support levels
        max_support_m30 = self.indicator_processor.get_max_support_m30()
        max_support_m15 = self.indicator_processor.get_max_support_m15()
        
        # Check for support breach
        below_m30_support = (max_support_m30 is not None and max_support_m30 > 0 and 
                           prev_close < max_support_m30 and 
                           current_close < self.indicator_processor.get_current_level_max())
        
        below_m15_support = (max_support_m15 is not None and max_support_m15 > 0 and 
                           prev_close < max_support_m15 and 
                           current_close < self.indicator_processor.get_current_level_max())
        
        # Check if price is rising (cancel condition)
        price_rising = prev_high < current_close
        if price_rising:
            return False
        
        # Setup detection
        sell_setup = below_m30_support or below_m15_support
        
        if sell_setup and self.config.print_scenario_details:
            print("SETUP DETECTED: Break And Close Sell - Price below support")
        
        # Check for bullish candles (cancel condition)
        patterns = self.indicator_processor.get_candle_patterns()
        if patterns.get('is_bullish', False):
            sell_setup = False
        
        # Get additional conditions
        without_wick = patterns.get('no_bottom_wick', False)
        lower_body = patterns.get('body_smaller', False)
        
        # Calculate pip differences
        pip_diff_low_close = PriceUtils.calculate_pip_difference(current_close, prev_low)
        
        min_resistance = self.indicator_processor.get_min_resistance_15()
        pips_to_resistance = float('inf')
        if min_resistance is not None:
            pips_to_resistance = PriceUtils.calculate_pip_difference(current_close, min_resistance)
        
        # Final conditions check
        current_level_max = self.indicator_processor.get_current_level_max()
        current_level_min = self.indicator_processor.get_current_level_min()
        
        if (sell_setup and 
            not without_wick and
            not lower_body and
            self.indicator_processor.is_in_significant_range() and
            prev_close < current_level_max and
            prev_high > current_level_max and
            prev_low > current_close and
            pips_to_resistance <= 60 and
            pip_diff_low_close < 20 and
            current_level_min is not None and current_level_min > 0):
            
            if self.config.print_scenario_details:
                print("Break And Close Sell trigger activated - executing sell trade")
            
            # Get stop loss
            stop_loss = self.indicator_processor.get_stop_loss_price_up()
            
            # Check wick distance
            lower_wick = self.indicator_processor.get_big_lower_wick_buffer()
            if (stop_loss is not None and lower_wick is not None and
                PriceUtils.calculate_pip_difference(current_close, lower_wick) >= 30):
                
                # Execute sell trade
                if self.trade_manager.execute_sell_trade(
                    stop_loss=stop_loss + (10 * 0.0001),
                    take_profit=current_level_min,
                    current_price=current_close
                ):
                    self.trade_executed_flag = True
        
        return sell_setup
    
    def check_break_and_close_buy(self, df: pd.DataFrame) -> bool:
        """
        Check for buy setup with focus on resistance break
        
        Returns:
            True if setup detected (not necessarily executed)
        """
        self.trade_executed_flag = False
        
        if df is None or len(df) < 2:
            return False
        
        # Get price data
        current_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        prev_high = df['high'].iloc[-2]
        prev_low = df['low'].iloc[-2]
        
        # Get resistance levels
        min_resistance_m30 = self.indicator_processor.get_min_resistance_30()
        min_resistance_m15 = self.indicator_processor.get_min_resistance_15()
        
        # Check for resistance break
        above_m30_resistance = (min_resistance_m30 is not None and min_resistance_m30 > 0 and
                              prev_close > min_resistance_m30 and
                              current_close > self.indicator_processor.get_current_level_min())
        
        above_m15_resistance = (min_resistance_m15 is not None and min_resistance_m15 > 0 and
                              prev_close > min_resistance_m15 and
                              current_close > self.indicator_processor.get_current_level_min())
        
        # Check if price is decreasing (cancel condition)
        price_decreasing = prev_low > current_close
        if price_decreasing:
            return False
        
        # Setup detection
        buy_setup = above_m30_resistance or above_m15_resistance
        
        if buy_setup and self.config.print_scenario_details:
            print("SETUP DETECTED: Break And Close Buy - Price above resistance")
        
        # Check for bearish candles (cancel condition)
        patterns = self.indicator_processor.get_candle_patterns()
        if patterns.get('is_bearish', False):
            buy_setup = False
        
        # Get additional conditions
        without_wick = patterns.get('no_top_wick', False)
        lower_body = patterns.get('body_smaller', False)
        
        # Calculate pip differences
        pip_diff_high_close = PriceUtils.calculate_pip_difference(current_close, prev_high)
        
        max_support = self.indicator_processor.get_max_support_m15()
        pips_to_support = float('inf')
        if max_support is not None:
            pips_to_support = PriceUtils.calculate_pip_difference(current_close, max_support)
        
        # Final conditions check
        current_level_min = self.indicator_processor.get_current_level_min()
        current_level_max = self.indicator_processor.get_current_level_max()
        
        if (buy_setup and
            not without_wick and
            not lower_body and
            self.indicator_processor.is_in_significant_range() and
            prev_close > current_level_min and
            prev_low < current_level_min and
            prev_high < current_close and
            pips_to_support <= 60 and
            pip_diff_high_close < 20 and
            current_level_max is not None and current_level_max > 0):
            
            if self.config.print_scenario_details:
                print("Break And Close Buy trigger activated - executing buy trade")
            
            # Get stop loss
            stop_loss = self.indicator_processor.get_stop_loss_price_down()
            
            # Check wick distance
            upper_wick = self.indicator_processor.get_big_upper_wick_buffer()
            if (stop_loss is not None and upper_wick is not None and
                PriceUtils.calculate_pip_difference(current_close, upper_wick) >= 30):
                
                # Execute buy trade
                if self.trade_manager.execute_buy_trade(
                    stop_loss=stop_loss - (10 * 0.0001),
                    take_profit=current_level_max,
                    current_price=current_close
                ):
                    self.trade_executed_flag = True
        
        return buy_setup
    
    def was_trade_executed(self) -> bool:
        """Check if trade was executed in last check"""
        return self.trade_executed_flag
    
    def reset_trade_executed(self):
        """Reset trade executed flag"""
        self.trade_executed_flag = False


# Example usage
if __name__ == "__main__":
    from .trading_system_core import create_sample_dataframe
    from risk_manager import RiskManager
    
    # Create components
    config = TradingConfig(print_scenario_details=True)
    df = create_sample_dataframe(days=5)
    
    # Create managers
    risk_mgr = RiskManager()
    processor = IndicatorProcessor(config)
    df_processed = processor.process_all_indicators(df)
    
    trade_mgr = TradeManager(config, processor, risk_mgr)
    
    # Create breakout scenarios
    breakout = BreakoutScenarios(config, trade_mgr, processor)
    
    # Check for setups
    print("Checking for breakout setups...")
    
    sell_setup = breakout.check_break_and_close_sell(df_processed)
    print(f"Sell setup detected: {sell_setup}")
    print(f"Trade executed: {breakout.was_trade_executed()}")
    
    breakout.reset_trade_executed()
    
    buy_setup = breakout.check_break_and_close_buy(df_processed)
    print(f"Buy setup detected: {buy_setup}")
    print(f"Trade executed: {breakout.was_trade_executed()}")
