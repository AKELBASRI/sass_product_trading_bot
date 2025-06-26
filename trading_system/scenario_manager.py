# scenario_manager.py
"""
Scenario Manager
Integrates all trading scenarios
Converted from ScenarioManager.mqh
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

from .trading_system_core import TradingConfig
from .indicator_processor import IndicatorProcessor
from .trade_manager import TradeManager
from .breakout_scenarios import BreakoutScenarios
from .trend_following_scenarios import TrendFollowingScenarios
from .counter_trend_scenarios import CounterTrendScenarios


class ScenarioManager:
    """
    Manages all trading scenarios and coordinates their execution
    """
    
    def __init__(self, config: TradingConfig, trade_manager: TradeManager,
                 indicator_processor: IndicatorProcessor):
        """
        Initialize scenario manager
        
        Args:
            config: Trading configuration
            trade_manager: Trade manager instance
            indicator_processor: Indicator processor instance
        """
        self.config = config
        self.trade_manager = trade_manager
        self.indicator_processor = indicator_processor
        
        # Create scenario instances
        self.breakout_scenarios = BreakoutScenarios(config, trade_manager, indicator_processor)
        self.trend_following_scenarios = TrendFollowingScenarios(config, trade_manager, indicator_processor)
        self.counter_trend_scenarios = CounterTrendScenarios(config, trade_manager, indicator_processor)
        
        # Trade tracking
        self.last_trade_bar_time: Optional[datetime] = None
        self.trade_executed_this_bar = False
        self.had_open_position_this_bar = False
        self.last_position_close_time: Optional[datetime] = None
        self.position_closed_this_bar = False
        
        # Setup flags
        self.sell_setup = False
        self.buy_setup = False
        
    def is_new_trading_bar(self, current_bar_time: datetime) -> bool:
        """Check if this is a new trading bar"""
        if current_bar_time != self.last_trade_bar_time:
            self._debug_print(f"New trading bar detected: {current_bar_time}")
            
            self.trade_executed_this_bar = False
            self.had_open_position_this_bar = self.trade_manager.has_open_positions()
            self.position_closed_this_bar = False
            
            return True
        return False
    
    def mark_trade_executed(self, current_bar_time: datetime):
        """Mark that a trade was executed in the current bar"""
        self.last_trade_bar_time = current_bar_time
        self.trade_executed_this_bar = True
        self.had_open_position_this_bar = True
        
        self._debug_print(f"Marked trade executed at {current_bar_time}")
    
    def can_trade_in_current_bar(self) -> bool:
        """Check if we can trade in this bar"""
        can_trade = not self.trade_executed_this_bar and not self.position_closed_this_bar
        
        if self.config.print_scenario_status:
            status = "Can trade in current bar" if can_trade else "Cannot trade in current bar"
            reason = ""
            if self.trade_executed_this_bar:
                reason = " (Trade already executed)"
            elif self.position_closed_this_bar:
                reason = " (Position closed this bar)"
            self._debug_print(status + reason)
        
        return can_trade
    
    def check_position_status(self):
        """Check if positions have been closed"""
        has_open_position = self.trade_manager.has_open_positions()
        
        # If we had a position but now don't, mark position closed
        if self.had_open_position_this_bar and not has_open_position:
            self.position_closed_this_bar = True
            self.last_position_close_time = datetime.now()
            
            self._debug_print(f"Position closed at {self.last_position_close_time}, "
                            "setting position closed flag for this bar")
        
        # Update position tracking
        self.had_open_position_this_bar = has_open_position
    
    def check_break_and_close_sell(self, df: pd.DataFrame) -> bool:
        """Check breakout sell scenario"""
        if not self.can_trade_in_current_bar():
            return False
        
        self.sell_setup = self.breakout_scenarios.check_break_and_close_sell(df)
        
        if self.sell_setup and self.breakout_scenarios.was_trade_executed():
            current_time = df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now()
            self.mark_trade_executed(current_time)
            self._debug_print("SCENARIO ACTIVATED: Break And Close Sell")
        
        return self.sell_setup
    
    def check_break_and_close_buy(self, df: pd.DataFrame) -> bool:
        """Check breakout buy scenario"""
        if not self.can_trade_in_current_bar():
            return False
        
        self.buy_setup = self.breakout_scenarios.check_break_and_close_buy(df)
        
        if self.buy_setup and self.breakout_scenarios.was_trade_executed():
            current_time = df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now()
            self.mark_trade_executed(current_time)
            self._debug_print("SCENARIO ACTIVATED: Break And Close Buy")
        
        return self.buy_setup
    
    def follow_trend_buy(self, df: pd.DataFrame) -> bool:
        """Check trend following buy scenario"""
        if not self.can_trade_in_current_bar():
            return False
        
        buy_setup = self.trend_following_scenarios.follow_trend_buy(df)
        
        if buy_setup and self.trend_following_scenarios.was_trade_executed():
            current_time = df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now()
            self.mark_trade_executed(current_time)
            self._debug_print("SCENARIO ACTIVATED: Follow Trend Buy")
        
        return buy_setup
    
    def follow_trend_sell(self, df: pd.DataFrame) -> bool:
        """Check trend following sell scenario"""
        if not self.can_trade_in_current_bar():
            return False
        
        sell_setup = self.trend_following_scenarios.follow_trend_sell(df)
        
        if sell_setup and self.trend_following_scenarios.was_trade_executed():
            current_time = df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now()
            self.mark_trade_executed(current_time)
            self._debug_print("SCENARIO ACTIVATED: Follow Trend Sell")
        
        return sell_setup
    
    def counter_trend_buy(self, df: pd.DataFrame) -> bool:
        """Check counter trend buy scenario"""
        if not self.can_trade_in_current_bar():
            return False
        
        buy_setup = self.counter_trend_scenarios.counter_trend_buy(df)
        
        if buy_setup and self.counter_trend_scenarios.was_trade_executed():
            current_time = df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now()
            self.mark_trade_executed(current_time)
            self._debug_print("SCENARIO ACTIVATED: Counter Trend Buy")
        
        return buy_setup
    
    def counter_trend_sell(self, df: pd.DataFrame) -> bool:
        """Check counter trend sell scenario"""
        if not self.can_trade_in_current_bar():
            return False
        
        sell_setup = self.counter_trend_scenarios.counter_trend_sell(df)
        
        if sell_setup and self.counter_trend_scenarios.was_trade_executed():
            current_time = df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now()
            self.mark_trade_executed(current_time)
            self._debug_print("SCENARIO ACTIVATED: Counter Trend Sell")
        
        return sell_setup
    
    def check_all_scenarios(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        Check all trading scenarios
        
        Returns:
            Dictionary with scenario results
        """
        results = {
            'breakout_sell': False,
            'breakout_buy': False,
            'trend_buy': False,
            'trend_sell': False,
            'counter_buy': False,
            'counter_sell': False,
            'trade_executed': False
        }
        
        # Check if trading is allowed for current session
        if not self.indicator_processor.is_trade_allowed_for_current_session() and not self.config.allow_all_sessions:
            self._debug_print("Trading not allowed in current session")
            return results
        
        # Check position status first
        self.check_position_status()
        
        # Only check scenarios if we can trade in current bar
        if self.can_trade_in_current_bar():
            # Check trend following strategies first
            results['trend_buy'] = self.follow_trend_buy(df)
            if not results['trend_buy']:
                results['trend_sell'] = self.follow_trend_sell(df)
            
            # Check counter trend strategies
            if not results['trend_buy'] and not results['trend_sell']:
                results['counter_buy'] = self.counter_trend_buy(df)
                if not results['counter_buy']:
                    results['counter_sell'] = self.counter_trend_sell(df)
            
            # Check breakout scenarios
            if not any([results['trend_buy'], results['trend_sell'], 
                       results['counter_buy'], results['counter_sell']]):
                results['breakout_sell'] = self.check_break_and_close_sell(df)
                if not results['breakout_sell']:
                    results['breakout_buy'] = self.check_break_and_close_buy(df)
            
            # Check if any trade was executed
            results['trade_executed'] = any([
                results['breakout_sell'] and self.breakout_scenarios.was_trade_executed(),
                results['breakout_buy'] and self.breakout_scenarios.was_trade_executed(),
                results['trend_buy'] and self.trend_following_scenarios.was_trade_executed(),
                results['trend_sell'] and self.trend_following_scenarios.was_trade_executed(),
                results['counter_buy'] and self.counter_trend_scenarios.was_trade_executed(),
                results['counter_sell'] and self.counter_trend_scenarios.was_trade_executed()
            ])
        else:
            self._debug_print("Skipping scenario checks - Cannot trade in current bar")
        
        return results
    
    def reset_all_scenarios(self):
        """Reset all scenario flags"""
        self.breakout_scenarios.reset_trade_executed()
        self.trend_following_scenarios.reset_trade_executed()
        self.counter_trend_scenarios.reset_trade_executed()
        
        self.sell_setup = False
        self.buy_setup = False
    
    def _debug_print(self, message: str):
        """Print debug message if enabled"""
        if self.config.print_scenario_status:
            print(f"SCENARIO MANAGER: {message}")


# Example usage
if __name__ == "__main__":
    from .trading_system_core import create_sample_dataframe
    from risk_manager import RiskManager
    
    # Create components
    config = TradingConfig(
        print_scenario_status=True,
        print_scenario_details=True,
        allow_all_sessions=True
    )
    
    df = create_sample_dataframe(days=5)
    
    # Create managers
    risk_mgr = RiskManager()
    processor = IndicatorProcessor(config)
    df_processed = processor.process_all_indicators(df)
    
    trade_mgr = TradeManager(config, processor, risk_mgr)
    
    # Create scenario manager
    scenario_mgr = ScenarioManager(config, trade_mgr, processor)
    
    # Simulate checking scenarios over multiple bars
    print("Simulating scenario checks over last 5 bars...")
    
    for i in range(-5, 0):
        current_bar_time = df_processed.index[i]
        
        # Check if new bar
        if scenario_mgr.is_new_trading_bar(current_bar_time):
            print(f"\n--- Bar {i}: {current_bar_time} ---")
            
            # Use slice of dataframe up to current bar
            df_slice = df_processed.iloc[:i+1]
            
            # Check all scenarios
            results = scenario_mgr.check_all_scenarios(df_slice)
            
            # Print results
            for scenario, result in results.items():
                if result:
                    print(f"  {scenario}: {result}")
            
            # Reset for next iteration
            scenario_mgr.reset_all_scenarios()
    
    # Show final positions
    print(f"\nFinal open positions: {len(trade_mgr.get_open_positions())}")
