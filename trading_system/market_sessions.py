# market_sessions.py
"""
Market Sessions Indicator
Converted from MarketSessions.mq5
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SessionInfo:
    """Information about a trading session"""
    name: str
    start_time: str  # "HH:MM" format
    end_time: str    # "HH:MM" format
    color: str
    show: bool
    trade: bool


class MarketSessionsIndicator:
    """
    Market sessions indicator showing major trading sessions
    """
    
    def __init__(self):
        # Session definitions
        self.sessions = [
            SessionInfo("Pre-Asian", "23:00", "01:00", "purple", True, False),
            SessionInfo("Asian", "01:00", "03:00", "red", True, False),
            SessionInfo("Pre-London", "03:00", "08:00", "orange", True, True),
            SessionInfo("London Open", "08:00", "11:00", "darkred", True, True),
            SessionInfo("Pre-New York", "11:00", "13:00", "lightblue", True, False),
            SessionInfo("New York Open", "13:00", "14:30", "blue", True, False),
            SessionInfo("London Close", "14:30", "20:00", "green", True, False),
        ]
        
        # Buffer to store session values
        self.session_buffer = None
        
    def _time_string_to_seconds(self, time_str: str) -> int:
        """Convert time string to seconds since midnight"""
        hours, minutes = map(int, time_str.split(':'))
        return hours * 3600 + minutes * 60
    
    def _is_in_session(self, dt: datetime, start_sec: int, end_sec: int) -> bool:
        """Check if datetime is within session range"""
        current_sec = dt.hour * 3600 + dt.minute * 60 + dt.second
        
        # Normal session (doesn't cross midnight)
        if start_sec <= end_sec:
            return start_sec <= current_sec <= end_sec
        # Session crosses midnight
        else:
            return current_sec >= start_sec or current_sec <= end_sec
    
    def get_active_session(self, dt: datetime) -> int:
        """
        Get the active session index for a given datetime
        Returns 0 if no active session, 1-7 for sessions
        """
        for i, session in enumerate(self.sessions):
            if not session.show:
                continue
                
            start_sec = self._time_string_to_seconds(session.start_time)
            end_sec = self._time_string_to_seconds(session.end_time)
            
            if self._is_in_session(dt, start_sec, end_sec):
                return i + 1  # Return 1-based index
                
        return 0  # No active session
    
    def get_session_name(self, session_value: int) -> str:
        """Get session name from buffer value"""
        if session_value <= 0 or session_value > len(self.sessions):
            return "No Active Session"
        return self.sessions[session_value - 1].name
    
    def is_trade_allowed(self, session_value: int) -> bool:
        """Check if trading is allowed in the current session"""
        if session_value <= 0 or session_value > len(self.sessions):
            return False
        return self.sessions[session_value - 1].trade
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate market sessions for the dataframe
        Adds 'session' column with session index (0-7)
        """
        # Create a copy to avoid modifying the original
        result_df = df.copy()
        
        # Calculate session for each row
        result_df['session'] = df.index.map(self.get_active_session)
        
        # Add session name for convenience
        result_df['session_name'] = result_df['session'].map(self.get_session_name)
        
        # Add trading allowed flag
        result_df['session_trade_allowed'] = result_df['session'].map(self.is_trade_allowed)
        
        return result_df
    
    def get_session_ranges(self, df: pd.DataFrame, lookback_bars: int = 500) -> Dict[str, Dict[str, float]]:
        """
        Calculate high/low ranges for each session over the lookback period
        """
        # Ensure we have session data
        if 'session' not in df.columns:
            df = self.calculate(df)
        
        # Limit lookback
        lookback_df = df.tail(lookback_bars)
        
        session_ranges = {}
        
        for i, session in enumerate(self.sessions, 1):
            # Filter data for this session
            session_data = lookback_df[lookback_df['session'] == i]
            
            if not session_data.empty:
                session_ranges[session.name] = {
                    'high': session_data['high'].max(),
                    'low': session_data['low'].min(),
                    'avg_volume': session_data['volume'].mean()
                }
            else:
                session_ranges[session.name] = {
                    'high': np.nan,
                    'low': np.nan,
                    'avg_volume': 0
                }
                
        return session_ranges
    
    def print_current_session(self, df: pd.DataFrame, index: int = -1):
        """Print information about the current session"""
        if 'session' not in df.columns:
            df = self.calculate(df)
            
        session_value = df.iloc[index]['session']
        session_name = self.get_session_name(session_value)
        trade_allowed = self.is_trade_allowed(session_value)
        
        print(f"Current Session: {session_name}")
        print(f"Trading Allowed: {'Yes' if trade_allowed else 'No'}")
        
        if session_value > 0:
            session_info = self.sessions[session_value - 1]
            print(f"Session Times: {session_info.start_time} - {session_info.end_time} GMT")


# Example usage
if __name__ == "__main__":
    from trading_system_core import create_sample_dataframe
    
    # Create sample data
    df = create_sample_dataframe(days=2)
    
    # Create indicator
    indicator = MarketSessionsIndicator()
    
    # Calculate sessions
    df_with_sessions = indicator.calculate(df)
    
    # Show recent data
    print("Recent market sessions:")
    print(df_with_sessions[['close', 'session', 'session_name', 'session_trade_allowed']].tail(10))
    
    # Get session ranges
    ranges = indicator.get_session_ranges(df_with_sessions)
    print("\nSession Ranges:")
    for session, data in ranges.items():
        if not np.isnan(data['high']):
            print(f"{session}: High={data['high']:.5f}, Low={data['low']:.5f}, "
                  f"Avg Volume={data['avg_volume']:.0f}")
    
    # Check current session
    print("\n" + "="*50)
    indicator.print_current_session(df_with_sessions)
