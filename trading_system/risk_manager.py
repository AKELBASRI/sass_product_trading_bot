# risk_manager.py
"""
Risk Manager
Converted from RiskManager.mqh
"""

import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TradeRecord:
    """Record of a completed trade"""
    symbol: str
    open_time: datetime
    close_time: datetime
    position_type: str  # 'BUY' or 'SELL'
    volume: float
    open_price: float
    close_price: float
    profit: float
    commission: float = 0.0
    swap: float = 0.0
    
    @property
    def net_profit(self) -> float:
        """Calculate net profit including commission and swap"""
        return self.profit - self.commission - self.swap


class RiskManager:
    """
    Manages daily profit/loss tracking and risk limits
    """
    
    def __init__(self, max_daily_loss: float = 90.0, max_daily_profit: float = 400.0,
                 enable_daily_limits: bool = False, base_risk_percent: float = 1.5):
        """
        Initialize risk manager
        
        Args:
            max_daily_loss: Maximum daily loss allowed
            max_daily_profit: Maximum daily profit allowed
            enable_daily_limits: Whether to enforce daily limits
            base_risk_percent: Base risk percentage for position sizing
        """
        self.max_daily_loss = max_daily_loss
        self.max_daily_profit = max_daily_profit
        self.enable_daily_limits = enable_daily_limits
        self.base_risk_percent = base_risk_percent
        
        # Daily P&L tracking
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.current_day = date.today()
        self.daily_limit_reached = False
        
        # Trade history
        self.trade_history: List[TradeRecord] = []
        
        # ATR data for dynamic risk calculation
        self.current_atr: Optional[float] = None
        self.average_atr: Optional[float] = None
        
    def _reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_profit = 0.0
        self.daily_loss = 0.0
        self.daily_limit_reached = False
        
    def _check_day_change(self):
        """Check if the day has changed and reset if needed"""
        current_day = date.today()
        if current_day != self.current_day:
            self.current_day = current_day
            self._reset_daily_stats()
            return True
        return False
    
    def add_trade(self, trade: TradeRecord):
        """Add a completed trade to history"""
        # Check for day change
        self._check_day_change()
        
        # Add to history
        self.trade_history.append(trade)
        
        # Update daily P&L if trade closed today
        if trade.close_time.date() == self.current_day:
            if trade.net_profit >= 0:
                self.daily_profit += trade.net_profit
            else:
                self.daily_loss += abs(trade.net_profit)
        
        # Check daily limits
        self._check_daily_limits()
    
    def _check_daily_limits(self):
        """Check if daily limits are reached"""
        if not self.enable_daily_limits:
            self.daily_limit_reached = False
            return
            
        # Check profit limit
        if self.daily_profit >= self.max_daily_profit:
            self.daily_limit_reached = True
            
        # Check loss limit
        if self.daily_loss >= self.max_daily_loss:
            self.daily_limit_reached = True
    
    def calculate_daily_pl(self, date_filter: Optional[date] = None) -> Dict[str, float]:
        """
        Calculate daily P&L from trade history
        
        Args:
            date_filter: Optional date to calculate P&L for (defaults to today)
            
        Returns:
            Dictionary with profit, loss, and net values
        """
        if date_filter is None:
            date_filter = self.current_day
            
        daily_profit = 0.0
        daily_loss = 0.0
        
        for trade in self.trade_history:
            if trade.close_time.date() == date_filter:
                if trade.net_profit >= 0:
                    daily_profit += trade.net_profit
                else:
                    daily_loss += abs(trade.net_profit)
        
        return {
            'profit': daily_profit,
            'loss': daily_loss,
            'net': daily_profit - daily_loss
        }
    
    def update(self):
        """Update daily P&L and check limits"""
        # Check for day change
        if self._check_day_change():
            # Recalculate today's P&L from history
            today_pl = self.calculate_daily_pl()
            self.daily_profit = today_pl['profit']
            self.daily_loss = today_pl['loss']
        
        # Check limits
        self._check_daily_limits()
    
    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed based on daily limits"""
        self.update()
        
        if not self.enable_daily_limits:
            return True
            
        return not self.daily_limit_reached
    
    def get_trading_restricted_reason(self) -> str:
        """Get reason why trading is restricted"""
        if not self.enable_daily_limits:
            return ""
            
        if self.daily_profit >= self.max_daily_profit:
            return f"Daily profit limit reached ({self.daily_profit:.2f} >= {self.max_daily_profit:.2f})"
            
        if self.daily_loss >= self.max_daily_loss:
            return f"Daily loss limit reached ({self.daily_loss:.2f} >= {self.max_daily_loss:.2f})"
            
        return ""
    
    def update_market_conditions(self, current_atr: float, average_atr: float):
        """Update market condition data for dynamic risk calculation"""
        self.current_atr = current_atr
        self.average_atr = average_atr
    
    def calculate_dynamic_risk_percent(self) -> float:
        """
        Calculate dynamic risk percentage based on market conditions
        
        Returns:
            Adjusted risk percentage
        """
        dynamic_risk = self.base_risk_percent
        
        # Adjust based on volatility if ATR data available
        if self.current_atr and self.average_atr:
            # Lower volatility = slightly higher risk
            if self.current_atr < self.average_atr * 0.8:
                dynamic_risk *= 1.2  # 20% increase
                
            # Higher volatility = lower risk
            elif self.current_atr > self.average_atr * 1.2:
                dynamic_risk *= 0.8  # 20% decrease
        
        # Adjust based on daily P&L
        if self.daily_profit > 0:
            # In profit for the day, can take slightly more risk
            dynamic_risk *= 1.1
        
        # Cap maximum risk
        return min(dynamic_risk, 2.5)  # Never exceed 2.5%
    
    def get_position_size_params(self, account_balance: float) -> Dict[str, float]:
        """
        Get position sizing parameters
        
        Returns:
            Dictionary with risk amount and risk percentage
        """
        risk_percent = self.calculate_dynamic_risk_percent()
        risk_amount = account_balance * risk_percent / 100
        
        return {
            'risk_percent': risk_percent,
            'risk_amount': risk_amount
        }
    
    def get_daily_stats(self) -> Dict[str, any]:
        """Get current daily statistics"""
        self.update()
        
        return {
            'date': self.current_day,
            'profit': self.daily_profit,
            'loss': self.daily_loss,
            'net': self.daily_profit - self.daily_loss,
            'trading_allowed': self.is_trading_allowed(),
            'limit_reached': self.daily_limit_reached,
            'restricted_reason': self.get_trading_restricted_reason()
        }
    
    def get_performance_summary(self, days: int = 30) -> Dict[str, any]:
        """Get performance summary for the last N days"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        daily_results = []
        total_profit = 0.0
        total_loss = 0.0
        winning_days = 0
        losing_days = 0
        
        # Calculate for each day
        current_date = start_date
        while current_date <= end_date:
            pl = self.calculate_daily_pl(current_date)
            
            if pl['net'] > 0:
                winning_days += 1
            elif pl['net'] < 0:
                losing_days += 1
                
            total_profit += pl['profit']
            total_loss += pl['loss']
            
            daily_results.append({
                'date': current_date,
                'profit': pl['profit'],
                'loss': pl['loss'],
                'net': pl['net']
            })
            
            current_date += timedelta(days=1)
        
        return {
            'period_days': days,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'net_pl': total_profit - total_loss,
            'winning_days': winning_days,
            'losing_days': losing_days,
            'win_rate': winning_days / (winning_days + losing_days) if (winning_days + losing_days) > 0 else 0,
            'daily_results': daily_results
        }
    
    def print_risk_status(self):
        """Print current risk management status"""
        stats = self.get_daily_stats()
        
        print("\n=== Risk Management Status ===")
        print(f"Date: {stats['date']}")
        print(f"Daily Profit: ${stats['profit']:.2f}")
        print(f"Daily Loss: ${stats['loss']:.2f}")
        print(f"Net P/L: ${stats['net']:.2f}")
        print(f"Trading Allowed: {'Yes' if stats['trading_allowed'] else 'No'}")
        
        if stats['restricted_reason']:
            print(f"Restriction Reason: {stats['restricted_reason']}")
        
        print(f"\nLimits:")
        print(f"  Max Daily Loss: ${self.max_daily_loss:.2f}")
        print(f"  Max Daily Profit: ${self.max_daily_profit:.2f}")
        print(f"  Limits Enabled: {'Yes' if self.enable_daily_limits else 'No'}")
        
        # Dynamic risk calculation
        risk_percent = self.calculate_dynamic_risk_percent()
        print(f"\nDynamic Risk: {risk_percent:.2f}% (base: {self.base_risk_percent:.2f}%)")


# Example usage
if __name__ == "__main__":
    # Create risk manager
    risk_mgr = RiskManager(
        max_daily_loss=90.0,
        max_daily_profit=400.0,
        enable_daily_limits=True
    )
    
    # Simulate some trades
    trades = [
        TradeRecord(
            symbol="EURUSD",
            open_time=datetime.now() - timedelta(hours=3),
            close_time=datetime.now() - timedelta(hours=2),
            position_type="BUY",
            volume=0.1,
            open_price=1.1000,
            close_price=1.1050,
            profit=50.0
        ),
        TradeRecord(
            symbol="EURUSD",
            open_time=datetime.now() - timedelta(hours=2),
            close_time=datetime.now() - timedelta(hours=1),
            position_type="SELL",
            volume=0.1,
            open_price=1.1050,
            close_price=1.1070,
            profit=-20.0
        ),
    ]
    
    # Add trades
    for trade in trades:
        risk_mgr.add_trade(trade)
    
    # Print status
    risk_mgr.print_risk_status()
    
    # Get performance summary
    summary = risk_mgr.get_performance_summary(days=7)
    print(f"\n7-Day Performance Summary:")
    print(f"Total Profit: ${summary['total_profit']:.2f}")
    print(f"Total Loss: ${summary['total_loss']:.2f}")
    print(f"Net P/L: ${summary['net_pl']:.2f}")
    print(f"Win Rate: {summary['win_rate']*100:.1f}%")
