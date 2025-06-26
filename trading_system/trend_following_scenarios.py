# trend_following_scenarios.py
"""
Trend Following Trading Scenarios
Converted from TrendFollowingScenarios.mqh
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from datetime import datetime

from .trading_system_core import TradingConfig, CandleUtils, PriceUtils
from .indicator_processor import IndicatorProcessor
from .trade_manager import TradeManager


class TrendFollowingScenarios:
    """
    Manages trend following trading scenarios
    """
    
    def __init__(self, config: TradingConfig, trade_manager: TradeManager, 
                 indicator_processor: IndicatorProcessor):
        """
        Initialize trend following scenarios
        
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
        
    def follow_trend_buy(self, df: pd.DataFrame) -> bool:
        """
        Follow trend buy method
        - Trend direction up
        - Bullish candle after bearish candle
        - In significant range
        
        Returns:
            True if setup detected (not necessarily executed)
        """
        self.trade_executed_flag = False
        
        if df is None or len(df) < 3:
            return False
        
        # Get price data
        current_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        prev_prev_close = df['close'].iloc[-3]
        prev_prev_open = df['open'].iloc[-3]
        
        # Get trend direction
        trend_info = self.indicator_processor.get_trend_info()
        trend_direction_30 = trend_info.get('trend_detector', {}).get('direction', 0)
        
        # Check if trend is up
        trend_up = trend_direction_30 == 1
        
        # Check if in significant range
        significant_range = self.indicator_processor.is_in_significant_range()
        
        # Get candle patterns
        patterns = self.indicator_processor.get_candle_patterns(-1)
        is_bullish_candle = patterns.get('is_bullish', False)
        without_top_wick = patterns.get('no_top_wick', False)
        
        # Check previous candle was bearish
        prev_patterns = self.indicator_processor.get_candle_patterns(-2)
        is_prev_bearish = prev_patterns.get('is_bearish', False)
        
        # Alternative check using raw data
        is_prev_prev_bearish = prev_prev_close < prev_prev_open
        
        # Can trade if bullish after bearish
        can_trade = (is_bullish_candle and is_prev_bearish) or (is_bullish_candle and is_prev_prev_bearish)
        
        # Get support distance
        max_support = self.indicator_processor.get_max_support_m30()
        pips_to_support = float('inf')
        if max_support is not None:
            pips_to_support = PriceUtils.calculate_pip_difference(current_close, max_support)
        
        # Check conditions
        buy_setup = False
        
        if (not without_top_wick and
            can_trade and
            significant_range and
            trend_up and
            self.indicator_processor.get_stop_loss_price_down() is not None):
            
            buy_setup = True
            
            if self.config.print_scenario_details:
                print("SETUP DETECTED: Follow Trend Buy")
            
            # Execute buy trade
            stop_loss = self.indicator_processor.get_stop_loss_price_down()
            take_profit = self.indicator_processor.get_current_level_max()
            
            if stop_loss is not None and take_profit is not None:
                if self.trade_manager.execute_buy_trade(
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    current_price=current_close
                ):
                    self.trade_executed_flag = True
        
        return buy_setup
    
    def follow_trend_sell(self, df: pd.DataFrame) -> bool:
        """
        Follow trend sell method
        - Trend direction down
        - Bearish candle after bullish candle
        - In significant range
        
        Returns:
            True if setup detected (not necessarily executed)
        """
        self.trade_executed_flag = False
        
        if df is None or len(df) < 3:
            return False
        
        # Get price data
        current_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        prev_prev_close = df['close'].iloc[-3]
        prev_prev_open = df['open'].iloc[-3]
        
        # Get trend direction
        trend_info = self.indicator_processor.get_trend_info()
        trend_direction_30 = trend_info.get('trend_detector', {}).get('direction', 0)
        
        # Check if trend is down
        trend_down = trend_direction_30 == -1
        
        # Check if in significant range
        significant_range = self.indicator_processor.is_in_significant_range()
        
        # Get candle patterns
        patterns = self.indicator_processor.get_candle_patterns(-1)
        is_bearish_candle = patterns.get('is_bearish', False)
        without_bottom_wick = patterns.get('no_bottom_wick', False)
        
        # Check previous candle was bullish
        prev_patterns = self.indicator_processor.get_candle_patterns(-2)
        is_prev_bullish = prev_patterns.get('is_bullish', False)
        
        # Alternative check using raw data
        is_prev_prev_bullish = prev_prev_close > prev_prev_open
        
        # Can trade if bearish after bullish
        can_trade = (is_bearish_candle and is_prev_bullish) or (is_bearish_candle and is_prev_prev_bullish)
        
        # Get resistance distance
        min_resistance = self.indicator_processor.get_min_resistance_30()
        pips_to_resistance = float('inf')
        if min_resistance is not None:
            pips_to_resistance = PriceUtils.calculate_pip_difference(current_close, min_resistance)
        
        # Check conditions
        sell_setup = False
        
        if (not without_bottom_wick and
            significant_range and
            trend_down and
            can_trade and
            self.indicator_processor.get_stop_loss_price_up() is not None):
            
            sell_setup = True
            
            if self.config.print_scenario_details:
                print("SETUP DETECTED: Follow Trend Sell")
            
            # Execute sell trade
            stop_loss = self.indicator_processor.get_stop_loss_price_up()
            take_profit = self.indicator_processor.get_current_level_min()
            
            if stop_loss is not None and take_profit is not None:
                if self.trade_manager.execute_sell_trade(
                    stop_loss=stop_loss,
                    take_profit=take_profit,
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
    
    # Modify some data to create trend following setup
    # Create an uptrend
    for i in range(len(df) - 20, len(df) - 3):
        df.loc[df.index[i], 'close'] = df.iloc[i]['open'] + 0.0005
        df.loc[df.index[i], 'high'] = df.iloc[i]['close'] + 0.0003
    
    # Create bearish candle followed by bullish candle
    df.loc[df.index[-3], 'close'] = df.iloc[-3]['open'] - 0.0008
    df.loc[df.index[-2], 'close'] = df.iloc[-2]['open'] - 0.0005
    df.loc[df.index[-1], 'close'] = df.iloc[-1]['open'] + 0.0010
    
    # Create managers
    risk_mgr = RiskManager()
    processor = IndicatorProcessor(config)
    df_processed = processor.process_all_indicators(df)
    
    trade_mgr = TradeManager(config, processor, risk_mgr)
    
    # Create trend following scenarios
    trend_following = TrendFollowingScenarios(config, trade_mgr, processor)
    
    # Check for setups
    print("Checking for trend following setups...")
    
    buy_setup = trend_following.follow_trend_buy(df_processed)
    print(f"Follow trend buy setup detected: {buy_setup}")
    print(f"Trade executed: {trend_following.was_trade_executed()}")
    
    trend_following.reset_trade_executed()
    
    sell_setup = trend_following.follow_trend_sell(df_processed)
    print(f"Follow trend sell setup detected: {sell_setup}")
    print(f"Trade executed: {trend_following.was_trade_executed()}")
