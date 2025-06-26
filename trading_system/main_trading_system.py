# main_trading_system.py
"""
Main Trading System
Integrates all components and provides the main entry point
Converted from AKELBASRI_SRB.mq5
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List

from .trading_system_core import TradingConfig, CandleUtils, create_sample_dataframe
from .indicator_processor import IndicatorProcessor
from .trade_manager import TradeManager
from .scenario_manager import ScenarioManager
from .risk_manager import RiskManager


class TradingSystem:
    """
    Main trading system that orchestrates all components
    """
    
    def __init__(self, config: TradingConfig, initial_balance: float = 10000.0):
        """
        Initialize the trading system
        
        Args:
            config: Trading configuration
            initial_balance: Initial account balance
        """
        self.config = config
        self.account_balance = initial_balance
        
        # Initialize components
        self.risk_manager = RiskManager(
            max_daily_loss=config.max_daily_loss,
            max_daily_profit=config.max_daily_profit,
            enable_daily_limits=config.enable_daily_limits,
            base_risk_percent=config.max_risk_percent
        )
        
        self.indicator_processor = IndicatorProcessor(config)
        
        self.trade_manager = TradeManager(
            config=config,
            indicator_processor=self.indicator_processor,
            risk_manager=self.risk_manager,
            account_balance=self.account_balance
        )
        
        self.scenario_manager = ScenarioManager(
            config=config,
            trade_manager=self.trade_manager,
            indicator_processor=self.indicator_processor
        )
        
        # State tracking
        self.last_processed_time: Optional[datetime] = None
        self.last_position_check_time: Optional[datetime] = None
        self.last_risk_check_time: Optional[datetime] = None
        self.tick_counter = 0
        self.tick_process_frequency = 5
        self.force_process = False
        
        # Debug tracking
        self.last_positions_total = 0
        
        print("MultiIndicatorEA initialized successfully")
        self._print_initialization_status()
    
    def _print_initialization_status(self):
        """Print initialization status"""
        # Risk parameters
        risk_status = "Trading allowed" if self.risk_manager.is_trading_allowed() else \
                     f"Trading restricted: {self.risk_manager.get_trading_restricted_reason()}"
        
        print("===== DAILY RISK PARAMETERS =====")
        print(f"Max Daily Loss: {self.config.max_daily_loss:.2f}")
        print(f"Max Daily Profit: {self.config.max_daily_profit:.2f}")
        
        daily_stats = self.risk_manager.get_daily_stats()
        print(f"Current P/L Status: Profit = {daily_stats['profit']:.2f}, "
              f"Loss = {daily_stats['loss']:.2f}, "
              f"Net = {daily_stats['net']:.2f}")
        print(f"Risk Status: {risk_status}")
        print("================================")
    
    def on_tick(self, df: pd.DataFrame, current_index: int = -1) -> Dict[str, Any]:
        """
        Main tick processing function
        
        Args:
            df: DataFrame with OHLCV data
            current_index: Index to process (default: last bar)
            
        Returns:
            Dictionary with processing results
        """
        results = {
            'processed': False,
            'new_trades': [],
            'closed_trades': [],
            'scenario_results': {},
            'risk_status': {}
        }
        
        # Apply tick throttling for backtesting
        if self._should_skip_tick(df, current_index):
            return results
        
        # Update risk management status
        self._update_risk_status()
        results['risk_status'] = self.risk_manager.get_daily_stats()
        
        # Check if trading is allowed
        if not self.risk_manager.is_trading_allowed():
            # Still manage open positions but don't open new ones
            self.trade_manager.manage_open_positions()
            results['processed'] = True
            return results
        
        # Process all indicators
        df_processed = self.indicator_processor.process_all_indicators(df)
        
        # Get current bar time
        current_bar_time = df.index[current_index]
        
        # Check for new trading bar
        self.scenario_manager.is_new_trading_bar(current_bar_time)
        
        # Debug position status
        self._debug_position_status()
        
        # Get fresh wick levels
        upper_wick_level = self.indicator_processor.get_big_upper_wick_buffer()
        lower_wick_level = self.indicator_processor.get_big_lower_wick_buffer()
        
        # Check and close positions on wick touch
        self.trade_manager.check_and_close_on_wick_touch(upper_wick_level, lower_wick_level)
        
        # Manage open positions
        self.trade_manager.manage_open_positions()
        
        # Check for level-based exits
        self.trade_manager.check_for_level_based_exit()
        
        # Check position status
        self.scenario_manager.check_position_status()
        
        # Check trading scenarios if allowed
        if (self.indicator_processor.is_trade_allowed_for_current_session(df_processed) or 
            self.config.allow_all_sessions):
            
            if self.scenario_manager.can_trade_in_current_bar():
                # Execute trading scenarios
                scenario_results = self.scenario_manager.check_all_scenarios(df_processed)
                results['scenario_results'] = scenario_results
                
                # Check for early exit conditions
                self._check_early_exit_conditions(df_processed, current_index)
                
                # Check for re-entry if enabled
                if self.config.reentry:
                    self._check_reentry_conditions(df_processed, current_index)
            else:
                if self.config.print_debug_info:
                    print("DEBUG: Skipping scenario checks - Cannot trade in current bar")
        
        results['processed'] = True
        return results
    
    def _should_skip_tick(self, df: pd.DataFrame, current_index: int) -> bool:
        """Check if we should skip processing this tick"""
        # For backtesting optimization
        self.tick_counter += 1
        
        # Get current bar time
        current_bar_time = df.index[current_index]
        
        # Check for new bar
        if self.last_processed_time != current_bar_time:
            self.force_process = True
            self.last_processed_time = current_bar_time
        elif self.tick_counter < self.tick_process_frequency and not self.force_process:
            return True
        
        # Reset counters
        self.tick_counter = 0
        self.force_process = False
        
        return False
    
    def _update_risk_status(self):
        """Update risk management status"""
        current_time = datetime.now()
        
        # Update risk status every minute
        if (self.last_risk_check_time is None or 
            current_time - self.last_risk_check_time >= timedelta(minutes=1)):
            
            self.risk_manager.update()
            self.last_risk_check_time = current_time
            
            if self.config.print_risk_info:
                stats = self.risk_manager.get_daily_stats()
                print(f"RISK UPDATE: Profit = {stats['profit']:.2f}, "
                      f"Loss = {stats['loss']:.2f}, "
                      f"Net = {stats['net']:.2f}")
                
                if not stats['trading_allowed']:
                    print(f"⚠️ TRADING RESTRICTED: {stats['restricted_reason']}")
    
    def _debug_position_status(self):
        """Debug position tracking"""
        if not self.config.print_debug_info:
            return
        
        current_time = datetime.now()
        current_positions_total = len(self.trade_manager.get_open_positions())
        
        # Only log if something changed or every 5 seconds
        if (current_positions_total != self.last_positions_total or 
            self.last_position_check_time is None or
            current_time - self.last_position_check_time >= timedelta(seconds=5)):
            
            self.last_position_check_time = current_time
            
            if current_positions_total != self.last_positions_total:
                change_type = "OPENED" if current_positions_total > self.last_positions_total else "CLOSED"
                print(f"DEBUG: Position count CHANGED from {self.last_positions_total} "
                      f"to {current_positions_total} - {change_type} at {current_time}")
            
            self.last_positions_total = current_positions_total
    
    def _check_early_exit_conditions(self, df: pd.DataFrame, current_index: int):
        """Check for early exit conditions"""
        # Get candle patterns
        patterns_current = self.indicator_processor.get_candle_patterns(current_index)
        is_bearish_current = patterns_current.get('is_bearish', False)
        is_bullish_current = patterns_current.get('is_bullish', False)
        
        # Early exit check
        self.trade_manager.check_early_exit(df, current_index)
    
    def _check_reentry_conditions(self, df: pd.DataFrame, current_index: int):
        """Check for re-entry conditions"""
        if current_index < 2:
            return
        
        # Get high/low values for re-entry logic
        current_high = df['high'].iloc[current_index]
        previous_high = df['high'].iloc[current_index - 1]
        current_low = df['low'].iloc[current_index]
        previous_low = df['low'].iloc[current_index - 1]
        
        # Note: Re-entry logic would be implemented in trade_manager
        # This is a placeholder for the re-entry check
        pass
    
    def run_backtest(self, df: pd.DataFrame, start_index: int = 100) -> Dict[str, Any]:
        """
        Run backtest on historical data
        
        Args:
            df: DataFrame with OHLCV data
            start_index: Index to start backtest from
            
        Returns:
            Dictionary with backtest results
        """
        print(f"Starting backtest from index {start_index} to {len(df)-1}")
        
        results = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0.0,
            'max_drawdown': 0.0,
            'trades': []
        }
        
        # Process each bar
        for i in range(start_index, len(df)):
            # Process tick
            tick_result = self.on_tick(df.iloc[:i+1], current_index=-1)
            
            # Track results
            if tick_result['scenario_results'].get('trade_executed', False):
                results['total_trades'] += 1
        
        # Get final statistics
        final_positions = self.trade_manager.get_open_positions()
        performance = self.risk_manager.get_performance_summary(days=30)
        
        results.update({
            'open_positions': len(final_positions),
            'performance_summary': performance,
            'final_balance': self.account_balance  # Simplified - would need P&L tracking
        })
        
        return results
    
    def print_status(self):
        """Print current system status"""
        print("\n=== TRADING SYSTEM STATUS ===")
        
        # Risk status
        self.risk_manager.print_risk_status()
        
        # Indicator status
        self.indicator_processor.print_summary()
        
        # Open positions
        positions = self.trade_manager.get_open_positions()
        print(f"\nOpen Positions: {len(positions)}")
        for pos in positions:
            print(f"  #{pos.ticket}: {pos.position_type.name} {pos.volume:.2f} lots "
                  f"@ {pos.open_price:.5f}, SL: {pos.stop_loss:.5f}, TP: {pos.take_profit:.5f}")


# Example usage and testing
if __name__ == "__main__":
    # Create configuration
    config = TradingConfig(
        print_scenario_details=True,
        print_risk_info=True,
        enable_daily_limits=True,
        allow_all_sessions=True
    )
    
    # Create sample data (replace with your live data)
    print("Creating sample data...")
    df = create_sample_dataframe(days=30)
    
    # Create trading system
    system = TradingSystem(config, initial_balance=10000.0)
    
    # Option 1: Process single tick (for live trading)
    print("\nProcessing current tick...")
    result = system.on_tick(df)
    print(f"Tick processed: {result['processed']}")
    print(f"Scenario results: {result['scenario_results']}")
    
    # Option 2: Run backtest
    print("\nRunning backtest...")
    backtest_results = system.run_backtest(df, start_index=500)
    
    print(f"\nBacktest Results:")
    print(f"Total trades: {backtest_results['total_trades']}")
    print(f"Open positions at end: {backtest_results['open_positions']}")
    
    # Print final status
    system.print_status()
    
    # Example of how to integrate with live data
    print("\n\n=== LIVE DATA INTEGRATION EXAMPLE ===")
    print("To use with live data, replace the DataFrame creation:")
    print("1. Connect to your data source (broker API, data provider, etc.)")
    print("2. Create DataFrame with columns: open, high, low, close, volume")
    print("3. Set DateTime index")
    print("4. Call system.on_tick(df) on each new tick/bar")
    print("\nExample:")
    print("df = pd.DataFrame(live_data)")
    print("df.index = pd.to_datetime(df['timestamp'])")
    print("result = system.on_tick(df)")
