# trade_manager.py
"""
Trade Manager
Handles trade execution, position management, and exit strategies
Converted from TradeManager.mqh
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .trading_system_core import (
    TradingConfig, Position, Trade, PositionType,
    PriceUtils, CandleUtils
)
from .indicator_processor import IndicatorProcessor
from .risk_manager import RiskManager, TradeRecord


class TradeManager:
    """
    Manages trade execution, position tracking, and exit strategies
    """
    
    def __init__(self, config: TradingConfig, indicator_processor: IndicatorProcessor,
                 risk_manager: RiskManager, account_balance: float = 10000.0):
        """
        Initialize trade manager
        
        Args:
            config: Trading configuration
            indicator_processor: Indicator processor instance
            risk_manager: Risk manager instance
            account_balance: Account balance for position sizing
        """
        self.config = config
        self.indicator_processor = indicator_processor
        self.risk_manager = risk_manager
        self.account_balance = account_balance
        
        # Position tracking
        self.positions: Dict[int, Position] = {}
        self.next_ticket = 1000
        
        # Track processed positions for various operations
        self.partial_close_executed: Dict[int, bool] = {}
        self.partial_close_loss_executed: Dict[int, bool] = {}
        self.breakeven_set: Dict[int, bool] = {}
        self.early_exit_executed: Dict[int, bool] = {}
        
        # Range tracking
        self.last_range_check_time: Optional[datetime] = None
        self.price_was_in_range = False
        
        # Re-entry tracking
        self.reentry_positions: Dict[int, int] = {}  # Original ticket -> reentry ticket
        
    def execute_buy_trade(self, stop_loss: float, take_profit: float,
                         symbol: str = "EURUSD", current_price: Optional[float] = None) -> bool:
        """
        Execute a buy trade
        
        Returns:
            True if trade executed successfully
        """
        # Check if trading is allowed
        if not self.risk_manager.is_trading_allowed():
            reason = self.risk_manager.get_trading_restricted_reason()
            print(f"BUY ORDER REJECTED: {reason}")
            return False
        
        # Check if price is in range
        if self._is_price_in_range():
            print("BUY ORDER REJECTED: Price is in range")
            return False
        
        # Get current price if not provided
        if current_price is None:
            if self.indicator_processor.df_processed is not None:
                current_price = self.indicator_processor.df_processed['close'].iloc[-1]
            else:
                print("BUY ORDER REJECTED: No price data available")
                return False
        
        # Validate stop loss
        if stop_loss >= current_price:
            # Generate dynamic stop loss
            stop_loss = self._calculate_dynamic_stop_loss(current_price, True)
            print(f"Generated dynamic stop loss for BUY at {stop_loss:.5f}")
        
        # Calculate position size
        sl_pips = PriceUtils.calculate_pip_difference(current_price, stop_loss)
        
        if sl_pips > self.config.maximum_sl_pips:
            print(f"BUY ORDER REJECTED: Stop loss exceeds maximum ({sl_pips:.1f} > {self.config.maximum_sl_pips})")
            return False
        
        # Get risk parameters
        risk_params = self.risk_manager.get_position_size_params(self.account_balance)
        risk_percent = risk_params['risk_percent']
        
        # Adjust risk based on trend
        trend_info = self.indicator_processor.get_trend_info()
        if trend_info.get('trend_detector', {}).get('direction', 0) == -1:
            risk_percent = self.config.min_risk_percent
            print("Entry with min risk due to opposing trend")
        
        # Calculate lot size
        risk_amount = self.account_balance * risk_percent / 100
        lot_size = PriceUtils.calculate_lot_size(
            risk_amount=risk_amount,
            stop_loss_pips=sl_pips,
            pip_value=10.0,  # Standard for most pairs
            min_lot=0.01,
            max_lot=100.0,
            lot_step=0.01
        )
        
        # Create position
        position = Position(
            ticket=self.next_ticket,
            symbol=symbol,
            position_type=PositionType.BUY,
            open_price=current_price,
            volume=lot_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            open_time=datetime.now()
        )
        
        # Add to positions
        self.positions[position.ticket] = position
        self.next_ticket += 1
        
        print(f"BUY ORDER EXECUTED: Ticket={position.ticket}, Lots={lot_size:.2f}, "
              f"Entry={current_price:.5f}, SL={stop_loss:.5f}, TP={take_profit:.5f}")
        
        return True
    
    def execute_sell_trade(self, stop_loss: float, take_profit: float,
                          symbol: str = "EURUSD", current_price: Optional[float] = None) -> bool:
        """
        Execute a sell trade
        
        Returns:
            True if trade executed successfully
        """
        # Check if trading is allowed
        if not self.risk_manager.is_trading_allowed():
            reason = self.risk_manager.get_trading_restricted_reason()
            print(f"SELL ORDER REJECTED: {reason}")
            return False
        
        # Check if price is in range
        if self._is_price_in_range():
            print("SELL ORDER REJECTED: Price is in range")
            return False
        
        # Get current price if not provided
        if current_price is None:
            if self.indicator_processor.df_processed is not None:
                current_price = self.indicator_processor.df_processed['close'].iloc[-1]
            else:
                print("SELL ORDER REJECTED: No price data available")
                return False
        
        # Validate stop loss
        if stop_loss <= current_price:
            # Generate dynamic stop loss
            stop_loss = self._calculate_dynamic_stop_loss(current_price, False)
            print(f"Generated dynamic stop loss for SELL at {stop_loss:.5f}")
        
        # Calculate position size
        sl_pips = PriceUtils.calculate_pip_difference(current_price, stop_loss)
        
        if sl_pips > self.config.maximum_sl_pips:
            print(f"SELL ORDER REJECTED: Stop loss exceeds maximum ({sl_pips:.1f} > {self.config.maximum_sl_pips})")
            return False
        
        # Get risk parameters
        risk_params = self.risk_manager.get_position_size_params(self.account_balance)
        risk_percent = risk_params['risk_percent']
        
        # Adjust risk based on trend
        trend_info = self.indicator_processor.get_trend_info()
        if trend_info.get('trend_detector', {}).get('direction', 0) == 1:
            risk_percent = self.config.min_risk_percent
            print("Entry with min risk due to opposing trend")
        
        # Calculate lot size
        risk_amount = self.account_balance * risk_percent / 100
        lot_size = PriceUtils.calculate_lot_size(
            risk_amount=risk_amount,
            stop_loss_pips=sl_pips,
            pip_value=10.0,
            min_lot=0.01,
            max_lot=100.0,
            lot_step=0.01
        )
        
        # Create position
        position = Position(
            ticket=self.next_ticket,
            symbol=symbol,
            position_type=PositionType.SELL,
            open_price=current_price,
            volume=lot_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            open_time=datetime.now()
        )
        
        # Add to positions
        self.positions[position.ticket] = position
        self.next_ticket += 1
        
        print(f"SELL ORDER EXECUTED: Ticket={position.ticket}, Lots={lot_size:.2f}, "
              f"Entry={current_price:.5f}, SL={stop_loss:.5f}, TP={take_profit:.5f}")
        
        return True
    
    def _is_price_in_range(self) -> bool:
        """Check if price is currently in a range"""
        if self.indicator_processor.df_processed is None:
            return False
            
        current_time = datetime.now()
        
        # Check if price is in range
        range_info = self.indicator_processor.get_range_info()
        price_in_range = range_info.get('active', False)
        
        if price_in_range:
            self.price_was_in_range = True
            self.last_range_check_time = current_time
            return True
        elif self.price_was_in_range:
            # Check if we have a new candle
            if self.last_range_check_time and (current_time - self.last_range_check_time) > timedelta(minutes=15):
                self.price_was_in_range = False
                print("New candle formed after price was in range - Trading enabled")
                return False
            else:
                print("Waiting for new candle after price was in range")
                return True
        
        return False
    
    def _calculate_dynamic_stop_loss(self, base_price: float, is_buy: bool) -> float:
        """Calculate dynamic stop loss based on ATR"""
        if self.indicator_processor.df_processed is None:
            # Default stop loss
            return base_price - 0.0070 if is_buy else base_price + 0.0070
        
        # Get ATR value
        atr = self.indicator_processor.df_processed.get('atr', pd.Series()).iloc[-1]
        if pd.isna(atr):
            atr = 0.0070  # Default
        
        # Calculate stop distance
        atr_multiplier = 2.0
        stop_distance = atr * atr_multiplier
        
        # Cap maximum stop distance
        max_stop_distance = self.config.maximum_sl_pips * 0.0001
        stop_distance = min(stop_distance, max_stop_distance)
        
        # Return stop loss price
        if is_buy:
            return base_price - stop_distance
        else:
            return base_price + stop_distance
    
    def manage_open_positions(self, current_price: Optional[float] = None):
        """Manage all open positions"""
        if current_price is None and self.indicator_processor.df_processed is not None:
            current_price = self.indicator_processor.df_processed['close'].iloc[-1]
        
        if current_price is None:
            return
        
        for ticket, position in list(self.positions.items()):
            # Calculate current profit in pips
            if position.position_type == PositionType.BUY:
                profit_pips = PriceUtils.calculate_pip_difference(current_price, position.open_price)
                if current_price < position.open_price:
                    profit_pips = -profit_pips
            else:
                profit_pips = PriceUtils.calculate_pip_difference(position.open_price, current_price)
                if current_price > position.open_price:
                    profit_pips = -profit_pips
            
            # Check for partial close on profit
            if (self.config.enable_partial_close_profit and 
                profit_pips >= self.config.partial_take_profit_pips and
                ticket not in self.partial_close_executed):
                
                self._execute_partial_close(position, self.config.partial_close_percent, "profit")
                self.partial_close_executed[ticket] = True
            
            # Check for partial close on loss
            if (self.config.enable_partial_close_loss and
                profit_pips <= -self.config.partial_close_loss_pips and
                ticket not in self.partial_close_loss_executed):
                
                self._execute_partial_close(position, self.config.partial_close_percent, "loss")
                self.partial_close_loss_executed[ticket] = True
            
            # Check for breakeven
            if (self.config.enable_breakeven and
                profit_pips >= self.config.partial_take_profit_pips and
                ticket not in self.breakeven_set):
                
                self._set_breakeven(position)
                self.breakeven_set[ticket] = True
            
            # Check trailing stop if breakeven was hit
            if (self.config.enable_trailing_stop and
                ticket in self.breakeven_set and
                self.breakeven_set[ticket]):
                
                self._update_trailing_stop(position, current_price)
    
    def _execute_partial_close(self, position: Position, percent: float, reason: str):
        """Execute partial close on a position"""
        close_volume = position.volume * percent / 100
        close_volume = round(close_volume / 0.01) * 0.01  # Round to lot step
        close_volume = min(close_volume, position.volume)
        
        print(f"Position #{position.ticket} partial close on {reason}: "
              f"{close_volume:.2f} lots ({percent}%)")
        
        # Update position volume
        position.volume -= close_volume
    
    def _set_breakeven(self, position: Position):
        """Set stop loss to breakeven"""
        buffer_points = self.config.breakeven_buffer_pips * 0.0001
        
        if position.position_type == PositionType.BUY:
            new_sl = position.open_price + buffer_points
        else:
            new_sl = position.open_price - buffer_points
        
        position.stop_loss = new_sl
        position.breakeven_hit = True
        
        print(f"Position #{position.ticket} stop loss moved to breakeven at {new_sl:.5f}")
    
    def _update_trailing_stop(self, position: Position, current_price: float):
        """Update trailing stop based on previous candle"""
        if self.indicator_processor.df_processed is None or len(self.indicator_processor.df_processed) < 2:
            return
        
        # Get previous candle
        prev_candle = self.indicator_processor.df_processed.iloc[-2]
        
        if position.position_type == PositionType.BUY:
            # For buy, use previous candle low
            new_sl = prev_candle['low']
            if new_sl > position.stop_loss:
                position.stop_loss = new_sl
                print(f"Trailing stop updated for BUY position #{position.ticket}: {new_sl:.5f}")
        else:
            # For sell, use previous candle high
            new_sl = prev_candle['high']
            if new_sl < position.stop_loss:
                position.stop_loss = new_sl
                print(f"Trailing stop updated for SELL position #{position.ticket}: {new_sl:.5f}")
    
    def check_early_exit(self, df: pd.DataFrame, index: int = -1):
        """Check for early exit conditions"""
        for ticket, position in list(self.positions.items()):
            if ticket in self.early_exit_executed:
                continue
            
            # Get candle patterns
            patterns = self.indicator_processor.get_candle_patterns(index)
            
            exit_condition = False
            exit_reason = ""
            
            if position.position_type == PositionType.BUY:
                # Exit buy on bearish candle or break of previous low
                if patterns.get('is_bearish', False):
                    exit_condition = True
                    exit_reason = "Bearish candle formed"
                elif index > 0 and df.iloc[index]['low'] < df.iloc[index-1]['low']:
                    exit_condition = True
                    exit_reason = "Previous low broken"
            else:
                # Exit sell on bullish candle or break of previous high
                if patterns.get('is_bullish', False):
                    exit_condition = True
                    exit_reason = "Bullish candle formed"
                elif index > 0 and df.iloc[index]['high'] > df.iloc[index-1]['high']:
                    exit_condition = True
                    exit_reason = "Previous high broken"
            
            if exit_condition:
                print(f"Early exit condition met for position #{ticket}: {exit_reason}")
                self._execute_partial_close(position, self.config.early_exit_close_percent, "early exit")
                self.early_exit_executed[ticket] = True
    
    def check_and_close_on_wick_touch(self, upper_wick_level: Optional[float], 
                                     lower_wick_level: Optional[float],
                                     current_price: Optional[float] = None):
        """Check and close positions if price touches fresh wick levels"""
        if current_price is None and self.indicator_processor.df_processed is not None:
            current_price = self.indicator_processor.df_processed['close'].iloc[-1]
        
        if current_price is None:
            return
        
        positions_to_close = []
        
        for ticket, position in self.positions.items():
            # Check upper wick touch (close buy positions)
            if (upper_wick_level is not None and 
                current_price >= upper_wick_level and
                position.position_type == PositionType.BUY):
                positions_to_close.append((ticket, "upper wick touched"))
            
            # Check lower wick touch (close sell positions)
            elif (lower_wick_level is not None and
                  current_price <= lower_wick_level and
                  position.position_type == PositionType.SELL):
                positions_to_close.append((ticket, "lower wick touched"))
        
        # Close positions
        for ticket, reason in positions_to_close:
            self.close_position(ticket, reason)
    
    def close_position(self, ticket: int, reason: str = ""):
        """Close a specific position"""
        if ticket not in self.positions:
            return
        
        position = self.positions[ticket]
        
        # Calculate final profit (simplified)
        current_price = self.indicator_processor.df_processed['close'].iloc[-1] if self.indicator_processor.df_processed is not None else position.open_price
        
        if position.position_type == PositionType.BUY:
            profit_pips = PriceUtils.calculate_pip_difference(current_price, position.open_price)
            profit = profit_pips * position.volume * 10  # Simplified calculation
        else:
            profit_pips = PriceUtils.calculate_pip_difference(position.open_price, current_price)
            profit = profit_pips * position.volume * 10
        
        # Create trade record for risk manager
        trade_record = TradeRecord(
            symbol=position.symbol,
            open_time=position.open_time,
            close_time=datetime.now(),
            position_type="BUY" if position.position_type == PositionType.BUY else "SELL",
            volume=position.volume,
            open_price=position.open_price,
            close_price=current_price,
            profit=profit
        )
        
        # Add to risk manager
        self.risk_manager.add_trade(trade_record)
        
        # Remove from positions
        del self.positions[ticket]
        
        # Clean up tracking dictionaries
        for tracking_dict in [self.partial_close_executed, self.partial_close_loss_executed,
                            self.breakeven_set, self.early_exit_executed]:
            tracking_dict.pop(ticket, None)
        
        print(f"Position #{ticket} closed: {reason}. Profit: {profit:.2f}")
    
    def get_open_positions(self) -> List[Position]:
        """Get list of open positions"""
        return list(self.positions.values())
    
    def has_open_positions(self) -> bool:
        """Check if there are any open positions"""
        return len(self.positions) > 0


# Example usage
if __name__ == "__main__":
    from .trading_system_core import create_sample_dataframe
    
    # Create components
    config = TradingConfig()
    df = create_sample_dataframe(days=2)
    
    # Create risk manager
    risk_mgr = RiskManager()
    
    # Create and process indicators
    processor = IndicatorProcessor(config)
    df_processed = processor.process_all_indicators(df)
    
    # Create trade manager
    trade_mgr = TradeManager(config, processor, risk_mgr)
    
    # Simulate a buy trade
    if trade_mgr.execute_buy_trade(
        stop_loss=df_processed['close'].iloc[-1] - 0.0050,
        take_profit=df_processed['close'].iloc[-1] + 0.0100
    ):
        print("\nOpen positions:", len(trade_mgr.get_open_positions()))
        
        # Simulate price movement and manage positions
        simulated_price = df_processed['close'].iloc[-1] + 0.0020
        print(f"\nSimulating price movement to {simulated_price:.5f}")
        trade_mgr.manage_open_positions(simulated_price)
