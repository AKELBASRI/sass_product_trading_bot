#!/bin/bash

# Fix imports in all Python files in the trading_system directory

cd /root/trading-system/trading_system/

# Fix imports in main_trading_system.py
sed -i 's/from trading_system_core import/from .trading_system_core import/g' main_trading_system.py
sed -i 's/from indicator_processor import/from .indicator_processor import/g' main_trading_system.py
sed -i 's/from trade_manager import/from .trade_manager import/g' main_trading_system.py
sed -i 's/from scenario_manager import/from .scenario_manager import/g' main_trading_system.py
sed -i 's/from risk_manager import/from .risk_manager import/g' main_trading_system.py

# Fix imports in indicator_processor.py
sed -i 's/from market_sessions import/from .market_sessions import/g' indicator_processor.py
sed -i 's/from detect_candles import/from .detect_candles import/g' indicator_processor.py
sed -i 's/from level_identification import/from .level_identification import/g' indicator_processor.py
sed -i 's/from supertrend import/from .supertrend import/g' indicator_processor.py
sed -i 's/from trend_detector import/from .trend_detector import/g' indicator_processor.py
sed -i 's/from detect_range import/from .detect_range import/g' indicator_processor.py
sed -i 's/from fresh_wicks import/from .fresh_wicks import/g' indicator_processor.py
sed -i 's/from candle_retracement import/from .candle_retracement import/g' indicator_processor.py
sed -i 's/from trading_system_core import/from .trading_system_core import/g' indicator_processor.py

# Fix imports in trade_manager.py
sed -i 's/from trading_system_core import/from .trading_system_core import/g' trade_manager.py
sed -i 's/from indicator_processor import/from .indicator_processor import/g' trade_manager.py
sed -i 's/from risk_manager import/from .risk_manager import/g' trade_manager.py

# Fix imports in scenario_manager.py
sed -i 's/from trading_system_core import/from .trading_system_core import/g' scenario_manager.py
sed -i 's/from indicator_processor import/from .indicator_processor import/g' scenario_manager.py
sed -i 's/from trade_manager import/from .trade_manager import/g' scenario_manager.py
sed -i 's/from breakout_scenarios import/from .breakout_scenarios import/g' scenario_manager.py
sed -i 's/from trend_following_scenarios import/from .trend_following_scenarios import/g' scenario_manager.py
sed -i 's/from counter_trend_scenarios import/from .counter_trend_scenarios import/g' scenario_manager.py

# Fix imports in breakout_scenarios.py
sed -i 's/from trading_system_core import/from .trading_system_core import/g' breakout_scenarios.py
sed -i 's/from indicator_processor import/from .indicator_processor import/g' breakout_scenarios.py
sed -i 's/from trade_manager import/from .trade_manager import/g' breakout_scenarios.py

# Fix imports in trend_following_scenarios.py
sed -i 's/from trading_system_core import/from .trading_system_core import/g' trend_following_scenarios.py
sed -i 's/from indicator_processor import/from .indicator_processor import/g' trend_following_scenarios.py
sed -i 's/from trade_manager import/from .trade_manager import/g' trend_following_scenarios.py

# Fix imports in counter_trend_scenarios.py
sed -i 's/from trading_system_core import/from .trading_system_core import/g' counter_trend_scenarios.py
sed -i 's/from indicator_processor import/from .indicator_processor import/g' counter_trend_scenarios.py
sed -i 's/from trade_manager import/from .trade_manager import/g' counter_trend_scenarios.py

echo "Import fixes completed!"
