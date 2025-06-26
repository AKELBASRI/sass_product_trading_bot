# counter_trend_scenarios.py
"""
Counter Trend Trading Scenarios
Converted from CounterTrendScenarios.mqh
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from datetime import datetime

from .trading_system_core import TradingConfig, CandleUtils, PriceUtils
from .indicator_processor import IndicatorProcessor
from .trade_manager import TradeManager


class CounterTrendScenarios:
    """
    Manages counter trend trading scenarios
    """
    
    def __init__(self, config: TradingConfig, trade_manager: TradeManager, 
                 indicator_processor: IndicatorProcessor):
        """
        Initialize counter trend scenarios
        
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
        
    def counter_trend_buy(self, df: pd.DataFrame) -> bool:
        """
        Counter trend buy method
        - trend direction down
        - candle with bottom wick
        - current price break the previous high
        
        Returns:
            True if setup detected (not necessarily executed)
        """
        self.trade_executed_flag = False
        
        if df is None or len(df) < 2:
            return False
        
        # Get price data
        current_close = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        prev_high = df['high'].iloc[-2]
        prev_low = df['low'].iloc[-2]
        
        # Get trend direction
        trend_info = self.indicator_processor.get_trend_info()
        trend_direction = trend_info.get('trend_detector', {}).get('direction', 0)
        
        # Check if trend is down
        down_trend = trend_direction == -1
        
        # Get candle patterns
        patterns = self.indicator_processor.get_candle_patterns()
        bottom_wick = patterns.get('has_bottom_wick', False)
        top_wick = patterns.get('has_top_wick', False)
        without_top_wick = patterns.get('no_top_wick', False)
        
        # Calculate recent move
        recent_move = PriceUtils.calculate_pip_difference(current_low, prev_high)
        if recent_move < 10:  # If price hasn't moved at least 10 pips
            return False
        
        # Check conditions
        buy_setup = False
        
        if (not without_top_wick and
            not top_wick and
            self.indicator_processor.is_in_significant_range() and
            ((current_close > prev_high and bottom_wick and not top_wick) or
             (current_close > prev_high and bottom_wick and not top_wick)) and
            current_close > prev_high and
            self.indicator_processor.get_current_level_max() is not None and
            self.indicator_processor.get_current_level_max() > 0):
            
            buy_setup = True
            
            if self.config.print_scenario_details:
                print("SETUP DETECTED: Counter Trend Buy")
            
            # Get stop loss
            stop_loss = self.indicator_processor.get_stop_loss_price_down()
            
            if stop_loss is not None:
                # Execute buy trade
                if self.trade_manager.execute_buy_trade(
                    stop_loss=stop_loss,
                    take_profit=self.indicator_processor.get_current_level_max(),
                    current_price=current_close
                ):
                    self.trade_executed_flag = True
        
        return buy_setup
    
    def counter_trend_sell(self, df: pd.DataFrame) -> bool:
        """
        Counter trend sell method
        - trend direction up
        - candle with top wick
        - current price break the previous low
        
        Returns:
            True if setup detected (not necessarily executed)
        """
        self.trade_executed_flag = False
        
        if df is None or len(df) < 2:
            return False
        
        # Get price data
        current_close = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        prev_high = df['high'].iloc[-2]
        prev_low = df['low'].iloc[-2]
        
        # Get trend direction
        trend_info = self.indicator_processor.get_trend_info()
        trend_direction = trend_info.get('trend_detector', {}).get('direction', 0)
        
        # Check if trend is up
        up_trend = trend_direction == 1
        
        # Get candle patterns
        patterns = self.indicator_processor.get_candle_patterns()
        top_wick = patterns.get('has_top_wick', False)
        bottom_wick = patterns.get('has_bottom_wick', False)
        without_bottom_wick = patterns.get('no_bottom_wick', False)
        
        # Calculate recent move
        recent_move = PriceUtils.calculate_pip_difference(current_low, prev_high)
        if recent_move < 10:  # If price hasn't moved at least 10 pips
            return False
        
        # Check conditions
        sell_setup = False
        
        if (not without_bottom_wick and
            not bottom_wick and
            self.indicator_processor.is_in_significant_range() and
            ((current_close < prev_low and top_wick and not bottom_wick) or
             (current_close < prev_low and top_wick and not bottom_wick)) and
            current_close < prev_low and
            self.indicator_processor.get_current_level_min() is not None and
            self.indicator_processor.get_current_level_min() > 0):
            
            sell_setup = True
            
            if self.config.print_scenario_details:
                print("SETUP DETECTED: Counter Trend Sell")
            
            # Get stop loss
            stop_loss = self.indicator_processor.get_stop_loss_price_up()
            
            if stop_loss is not None:
                # Execute sell trade
                if self.trade_manager.execute_sell_trade(
                    stop_loss=stop_loss,
                    take_profit=self.indicator_processor.get_current_level_min(),
                    current_price=current_close
                ):
                    self.trade_executed_flag = True
        
        return sell_setup
    
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
    
    # Modify some data to create counter trend setups
    # Create a downtrend with a bullish reversal candle
    for i in range(len(df) - 10, len(df) - 2):
        df.loc[df.index[i], 'close'] = df.iloc[i]['open'] - 0.0010
        df.loc[df.index[i], 'low'] = df.iloc[i]['close'] - 0.0005
    
    # Create bottom wick on last candle and price break
    df.loc[df.index[-1], 'low'] = df.iloc[-1]['open'] - 0.0015
    df.loc[df.index[-1], 'close'] = df.iloc[-2]['high'] + 0.0005
    
    # Create managers
    risk_mgr = RiskManager()
    processor = IndicatorProcessor(config)
    df_processed = processor.process_all_indicators(df)
    
    trade_mgr = TradeManager(config, processor, risk_mgr)
    
    # Create counter trend scenarios
    counter_trend = CounterTrendScenarios(config, trade_mgr, processor)
    
    # Check for setups
    print("Checking for counter trend setups...")
    
    buy_setup = counter_trend.counter_trend_buy(df_processed)
    print(f"Counter trend buy setup detected: {buy_setup}")
    print(f"Trade executed: {counter_trend.was_trade_executed()}")
    
    counter_trend.reset_trade_executed()
    
    sell_setup = counter_trend.counter_trend_sell(df_processed)
    print(f"Counter trend sell setup detected: {sell_setup}")
    print(f"Trade executed: {counter_trend.was_trade_executed()}")
