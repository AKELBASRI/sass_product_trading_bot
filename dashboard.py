# enhanced_dashboard.py
"""
Enhanced Trading Dashboard with TradingView Lightweight Charts, ML, and Fundamental Analysis
"""

import streamlit as st
import pandas as pd
import numpy as np
import redis
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import requests
from streamlit_lightweight_charts import renderLightweightCharts
import ta
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Advanced Trading System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional trading interface
st.markdown("""
<style>
    /* Dark theme styling */
    .stApp {
        background-color: #0a0e1a;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1a1e2e 0%, #252a3e 100%);
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 212, 255, 0.1);
    }
    
    .metric-card {
        background: #1a1e2e;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #252a3e;
        margin-bottom: 10px;
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        border-color: #00d4ff;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.3);
    }
    
    .indicator-badge {
        display: inline-block;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        margin: 2px;
    }
    
    .badge-active {
        background: #00d4ff20;
        color: #00d4ff;
        border: 1px solid #00d4ff40;
    }
    
    .badge-resistance {
        background: #ff386020;
        color: #ff3860;
        border: 1px solid #ff386040;
    }
    
    .badge-support {
        background: #00ff8820;
        color: #00ff88;
        border: 1px solid #00ff8840;
    }
    
    .ml-prediction {
        background: linear-gradient(135deg, #00d4ff20, #00ff8820);
        border: 2px solid #00d4ff;
        border-radius: 15px;
        padding: 30px;
        text-align: center;
        margin: 20px 0;
    }
    
    .prediction-value {
        font-size: 48px;
        font-weight: 700;
        margin: 10px 0;
    }
    
    .confidence-bar {
        width: 100%;
        height: 10px;
        background: #252a3e;
        border-radius: 5px;
        overflow: hidden;
        margin-top: 10px;
    }
    
    .confidence-fill {
        height: 100%;
        background: linear-gradient(90deg, #00ff88, #00d4ff);
        border-radius: 5px;
        transition: width 0.5s ease;
    }
    
    /* Trading levels styling */
    .level-item {
        display: flex;
        justify-content: space-between;
        padding: 10px;
        background: #252a3e;
        border-radius: 8px;
        margin-bottom: 8px;
        border-left: 3px solid;
    }
    
    .level-resistance {
        border-left-color: #ff3860;
    }
    
    .level-support {
        border-left-color: #00ff88;
    }
    
    /* Fundamental event styling */
    .fundamental-event {
        padding: 15px;
        background: #1a1e2e;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 4px solid;
    }
    
    .event-high {
        border-left-color: #ff3860;
    }
    
    .event-medium {
        border-left-color: #ff9800;
    }
    
    .event-low {
        border-left-color: #4caf50;
    }
</style>
""", unsafe_allow_html=True)


class EnhancedTradingDashboard:
    """Enhanced dashboard with TradingView Lightweight Charts, ML, and fundamental analysis"""
    
    def __init__(self):
        # Redis connection
        self.redis_client = redis.Redis(
            host=st.secrets.get("REDIS_HOST", "redis"),
            port=st.secrets.get("REDIS_PORT", 6379),
            decode_responses=True
        )
        
        # Backend API URL
        self.api_url = st.secrets.get("API_URL", "http://trading-backend:8000")
        
        # Initialize session state
        self._init_session_state()
        
        # Available symbols
        self.symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD']
        
    def _init_session_state(self):
        """Initialize session state variables"""
        if 'selected_symbol' not in st.session_state:
            st.session_state.selected_symbol = 'EURUSD'
        if 'selected_timeframe' not in st.session_state:
            st.session_state.selected_timeframe = '15M'
        if 'show_indicators' not in st.session_state:
            st.session_state.show_indicators = {
                'levels': True,
                'supertrend': True,
                'sessions': True,
                'wicks': False,
                'ranges': False,
                'ml_prediction': True,
                'volume': True
            }
        if 'min_pips_distance' not in st.session_state:
            st.session_state.min_pips_distance = 10
    
    def render_header(self):
        """Render main header with symbol and timeframe selection"""
        st.markdown('<div class="main-header">', unsafe_allow_html=True)
        
        col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1, 1])
        
        with col1:
            st.markdown("# 📊 Advanced Trading System", unsafe_allow_html=True)
            st.markdown("**Real-time Analysis with ML & Fundamentals**", unsafe_allow_html=True)
        
        with col2:
            st.session_state.selected_symbol = st.selectbox(
                "Symbol",
                self.symbols,
                index=self.symbols.index(st.session_state.selected_symbol),
                key="symbol_select"
            )
        
        with col3:
            timeframes = ['1M', '5M', '15M', '30M', '1H', '4H', '1D']
            st.session_state.selected_timeframe = st.selectbox(
                "Timeframe",
                timeframes,
                index=timeframes.index(st.session_state.selected_timeframe),
                key="timeframe_select"
            )
        
        with col4:
            current_price = self.get_current_price()
            if current_price:
                st.metric(
                    "Current Price",
                    f"{current_price:.5f}",
                    delta=None
                )
        
        with col5:
            status = self.get_connection_status()
            if status:
                st.success("● Connected")
            else:
                st.error("● Disconnected")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_tradingview_chart(self):
        """Render TradingView Lightweight Chart"""
        st.markdown("### 📈 Advanced Chart Analysis")
        
        # Get market data
        df = self.get_market_data()
        if df.empty:
            st.warning("No market data available")
            return
        
        # Calculate indicators
        levels = self.calculate_support_resistance_levels(df)
        supertrend = self.calculate_supertrend(df)
        sessions = self.calculate_market_sessions(df)
        wicks = self.calculate_fresh_wicks(df)
        ranges = self.calculate_ranges(df)
        
        # Prepare chart data
        chart_data = []
        for idx, row in df.iterrows():
            chart_data.append({
                'time': int(idx.timestamp()),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close'])
            })
        
        # Prepare volume data
        volume_data = []
        for idx, row in df.iterrows():
            color = '#ff3860' if row['close'] < row['open'] else '#00ff88'
            volume_data.append({
                'time': int(idx.timestamp()),
                'value': float(row['volume']),
                'color': color
            })
        
        # Prepare indicators data
        indicators = []
        markers = []
        
        # Add SuperTrend if enabled
        if st.session_state.show_indicators['supertrend'] and len(supertrend) > 0:
            supertrend_data = []
            for i in range(len(df) - len(supertrend), len(df)):
                supertrend_data.append({
                    'time': int(df.index[i].timestamp()),
                    'value': float(supertrend[i - (len(df) - len(supertrend))])
                })
            indicators.append({
                'title': 'SuperTrend',
                'data': supertrend_data,
                'color': '#00d4ff',
                'lineWidth': 3
            })
        
        # Add horizontal lines for support/resistance
        horizontal_lines = []
        
        if st.session_state.show_indicators['levels']:
            # Add resistance levels
            for i, level in enumerate(levels['resistance'][:5]):
                horizontal_lines.append({
                    'price': level['price'],
                    'color': '#ff3860',
                    'lineWidth': 2,
                    'lineStyle': 2,  # Dashed
                    'title': f'R{i+1}'
                })
            
            # Add support levels
            for i, level in enumerate(levels['support'][:5]):
                horizontal_lines.append({
                    'price': level['price'],
                    'color': '#00ff88',
                    'lineWidth': 2,
                    'lineStyle': 2,  # Dashed
                    'title': f'S{i+1}'
                })
        
        # Add wick levels if enabled
        if st.session_state.show_indicators['wicks']:
            if wicks['upper']:
                horizontal_lines.append({
                    'price': wicks['upper']['price'],
                    'color': '#ff9800',
                    'lineWidth': 2,
                    'lineStyle': 1,  # Dotted
                    'title': 'Upper Wick'
                })
            
            if wicks['lower']:
                horizontal_lines.append({
                    'price': wicks['lower']['price'],
                    'color': '#2196f3',
                    'lineWidth': 2,
                    'lineStyle': 1,  # Dotted
                    'title': 'Lower Wick'
                })
        
        # Chart options
        chart_options = {
            'layout': {
                'background': {'color': '#0a0e1a'},
                'textColor': '#d1d4dc',
                'fontSize': 12
            },
            'grid': {
                'vertLines': {'color': '#1a1e2e'},
                'horzLines': {'color': '#1a1e2e'}
            },
            'crosshair': {
                'mode': 1  # Normal mode
            },
            'rightPriceScale': {
                'borderColor': '#1a1e2e'
            },
            'timeScale': {
                'borderColor': '#1a1e2e',
                'timeVisible': True,
                'secondsVisible': False
            }
        }
        
        # Prepare series options
        series = [
            {
                'type': 'candlestick',
                'data': chart_data,
                'upColor': '#00ff88',
                'downColor': '#ff3860',
                'borderVisible': True,
                'wickUpColor': '#00ff88',
                'wickDownColor': '#ff3860'
            }
        ]
        
        # Add volume if enabled
        if st.session_state.show_indicators['volume']:
            series.append({
                'type': 'histogram',
                'data': volume_data,
                'priceFormat': {
                    'type': 'volume'
                },
                'priceScaleId': 'volume',
                'scaleMargins': {
                    'top': 0.8,
                    'bottom': 0
                }
            })
        
        # Add line series for indicators
        for indicator in indicators:
            series.append({
                'type': 'line',
                'data': indicator['data'],
                'color': indicator['color'],
                'lineWidth': indicator['lineWidth'],
                'title': indicator['title']
            })
        
        # Render the chart
        renderLightweightCharts([
            {
                'chart': chart_options,
                'series': series,
                'horizontalLines': horizontal_lines
            }
        ], 'main_chart')
    
    def calculate_support_resistance_levels(self, df: pd.DataFrame) -> Dict[str, List]:
        """Calculate support and resistance levels using the custom method"""
        levels = {'resistance': [], 'support': []}
        min_distance = st.session_state.min_pips_distance * 0.0001
        
        # Look for patterns in the data
        for i in range(1, len(df) - 1):
            prev = df.iloc[i - 1]
            curr = df.iloc[i]
            
            # Resistance: Bullish candle followed by bearish candle
            if prev['close'] > prev['open'] and curr['close'] < curr['open']:
                level = curr['open']
                
                # Check minimum distance from existing levels
                too_close = False
                for existing in levels['resistance']:
                    if abs(level - existing['price']) < min_distance:
                        too_close = True
                        break
                
                if not too_close:
                    levels['resistance'].append({
                        'price': level,
                        'time': df.index[i],
                        'strength': self.calculate_level_strength(df, level, i)
                    })
            
            # Support: Bearish candle followed by bullish candle
            if prev['close'] < prev['open'] and curr['close'] > curr['open']:
                level = curr['open']
                
                too_close = False
                for existing in levels['support']:
                    if abs(level - existing['price']) < min_distance:
                        too_close = True
                        break
                
                if not too_close:
                    levels['support'].append({
                        'price': level,
                        'time': df.index[i],
                        'strength': self.calculate_level_strength(df, level, i)
                    })
        
        # Sort levels by strength and price
        levels['resistance'].sort(key=lambda x: (-x['strength'], x['price']))
        levels['support'].sort(key=lambda x: (-x['strength'], -x['price']))
        
        return levels
    
    def calculate_level_strength(self, df: pd.DataFrame, level: float, start_idx: int) -> int:
        """Calculate how many times a level has been tested"""
        touches = 0
        tolerance = 0.0001  # 1 pip tolerance
        
        for i in range(start_idx, len(df)):
            if (abs(df.iloc[i]['high'] - level) < tolerance or
                abs(df.iloc[i]['low'] - level) < tolerance or
                abs(df.iloc[i]['open'] - level) < tolerance or
                abs(df.iloc[i]['close'] - level) < tolerance):
                touches += 1
        
        return touches
    
    def calculate_supertrend(self, df: pd.DataFrame, period: int = 10, multiplier: int = 3) -> List[float]:
        """Calculate SuperTrend indicator"""
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = true_range.rolling(period).mean()
        
        # Calculate basic bands
        hl2 = (df['high'] + df['low']) / 2
        final_upperband = hl2 + (multiplier * atr)
        final_lowerband = hl2 - (multiplier * atr)
        
        # Initialize Supertrend
        supertrend = []
        
        for i in range(period, len(df)):
            if df['close'].iloc[i] <= final_upperband.iloc[i]:
                supertrend.append(final_upperband.iloc[i])
            else:
                supertrend.append(final_lowerband.iloc[i])
        
        return supertrend
    
    def calculate_market_sessions(self, df: pd.DataFrame) -> Dict:
        """Calculate market sessions"""
        sessions = {
            'Asian': {'start': '01:00', 'end': '09:00'},
            'London': {'start': '08:00', 'end': '16:00'},
            'New York': {'start': '13:00', 'end': '21:00'}
        }
        return sessions
    
    def calculate_fresh_wicks(self, df: pd.DataFrame) -> Dict:
        """Calculate fresh wick levels that haven't been tested"""
        min_wick_size = 0.0003  # 3 pips minimum
        upper_wick = None
        lower_wick = None
        
        # Look for significant wicks in recent candles
        for i in range(max(0, len(df) - 50), len(df) - 1):
            candle = df.iloc[i]
            body = abs(candle['close'] - candle['open'])
            upper_wick_size = candle['high'] - max(candle['open'], candle['close'])
            lower_wick_size = min(candle['open'], candle['close']) - candle['low']
            
            # Check for significant upper wick
            if upper_wick_size > min_wick_size and upper_wick_size > body * 0.5:
                tested = False
                for j in range(i + 1, len(df)):
                    if df.iloc[j]['high'] >= candle['high']:
                        tested = True
                        break
                if not tested:
                    upper_wick = {'price': candle['high'], 'time': df.index[i]}
            
            # Check for significant lower wick
            if lower_wick_size > min_wick_size and lower_wick_size > body * 0.5:
                tested = False
                for j in range(i + 1, len(df)):
                    if df.iloc[j]['low'] <= candle['low']:
                        tested = True
                        break
                if not tested:
                    lower_wick = {'price': candle['low'], 'time': df.index[i]}
        
        return {'upper': upper_wick, 'lower': lower_wick}
    
    def calculate_ranges(self, df: pd.DataFrame) -> Optional[Dict]:
        """Calculate price ranges"""
        min_candles_in_range = 10
        
        for i in range(max(0, len(df) - 100), len(df) - min_candles_in_range):
            range_high = df.iloc[i]['high']
            range_low = df.iloc[i]['low']
            candles_in_range = 0
            
            for j in range(i, len(df)):
                if df.iloc[j]['high'] <= range_high and df.iloc[j]['low'] >= range_low:
                    candles_in_range += 1
                else:
                    break
            
            if candles_in_range >= min_candles_in_range:
                return {
                    'high': range_high,
                    'low': range_low,
                    'start': df.index[i],
                    'end': df.index[i + candles_in_range - 1]
                }
        
        return None
    
    def render_ml_prediction(self):
        """Render ML prediction panel"""
        st.markdown("### 🤖 Machine Learning Analysis")
        
        # Simulated ML prediction
        prediction = np.random.choice(['BUY', 'SELL', 'HOLD'], p=[0.4, 0.3, 0.3])
        confidence = np.random.uniform(60, 95)
        
        # Display prediction
        st.markdown('<div class="ml-prediction">', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            if prediction == 'BUY':
                st.markdown('<div class="prediction-value" style="color: #00ff88;">BUY</div>', 
                          unsafe_allow_html=True)
            elif prediction == 'SELL':
                st.markdown('<div class="prediction-value" style="color: #ff3860;">SELL</div>', 
                          unsafe_allow_html=True)
            else:
                st.markdown('<div class="prediction-value" style="color: #ffd700;">HOLD</div>', 
                          unsafe_allow_html=True)
            
            st.markdown(f"**Confidence:** {confidence:.1f}%")
            
            # Confidence bar
            st.markdown(f"""
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: {confidence}%;"></div>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    def render_fundamental_analysis(self):
        """Render fundamental analysis panel"""
        st.markdown("### 📰 Fundamental Analysis")
        
        # Simulated economic events
        events = [
            {
                'title': 'ECB Interest Rate Decision',
                'impact': 'high',
                'currency': 'EUR',
                'time': 'Today 14:30',
                'expected': '4.25%',
                'previous': '4.00%'
            },
            {
                'title': 'US Non-Farm Payrolls',
                'impact': 'medium',
                'currency': 'USD',
                'time': 'Tomorrow 13:30',
                'expected': '185K',
                'previous': '187K'
            },
            {
                'title': 'UK GDP Growth Rate',
                'impact': 'low',
                'currency': 'GBP',
                'time': 'Monday 09:30',
                'expected': '0.2%',
                'previous': '0.1%'
            }
        ]
        
        for event in events:
            impact_class = f"event-{event['impact']}"
            st.markdown(f"""
                <div class="fundamental-event {impact_class}">
                    <h4>{event['title']} <span class="indicator-badge badge-active">{event['impact'].upper()}</span></h4>
                    <p style="margin: 5px 0; color: #8892a6;">
                        {event['time']} • Currency: {event['currency']}<br>
                        Expected: {event['expected']} • Previous: {event['previous']}
                    </p>
                </div>
            """, unsafe_allow_html=True)
    
    def render_levels_panel(self):
        """Render support/resistance levels panel"""
        st.markdown("### 📍 Key Price Levels")
        
        df = self.get_market_data()
        if df.empty:
            st.warning("No data available")
            return
        
        levels = self.calculate_support_resistance_levels(df)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Resistance Levels")
            for i, level in enumerate(levels['resistance'][:5]):
                st.markdown(f"""
                    <div class="level-item level-resistance">
                        <span>R{i+1}</span>
                        <span>{level['price']:.5f}</span>
                    </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("#### Support Levels")
            for i, level in enumerate(levels['support'][:5]):
                st.markdown(f"""
                    <div class="level-item level-support">
                        <span>S{i+1}</span>
                        <span>{level['price']:.5f}</span>
                    </div>
                """, unsafe_allow_html=True)
    
    def render_indicator_controls(self):
        """Render indicator control panel"""
        st.sidebar.markdown("### 📊 Indicator Settings")
        
        # Indicator toggles
        st.sidebar.markdown("#### Active Indicators")
        
        indicators = {
            'levels': 'Support/Resistance Levels',
            'supertrend': 'SuperTrend',
            'sessions': 'Market Sessions',
            'wicks': 'Fresh Wicks',
            'ranges': 'Range Detection',
            'ml_prediction': 'ML Predictions',
            'volume': 'Volume'
        }
        
        for key, label in indicators.items():
            st.session_state.show_indicators[key] = st.sidebar.checkbox(
                label,
                value=st.session_state.show_indicators[key],
                key=f"indicator_{key}"
            )
        
        # Level identification settings
        st.sidebar.markdown("#### Level Identification")
        st.session_state.min_pips_distance = st.sidebar.slider(
            "Min Distance (pips)",
            min_value=5,
            max_value=50,
            value=st.session_state.min_pips_distance,
            step=5
        )
    
    def get_market_data(self) -> pd.DataFrame:
        """Get market data from Redis"""
        try:
            timeframe_map = {
                '1M': 1, '5M': 5, '15M': 15, '30M': 30,
                '1H': 60, '4H': 240, '1D': 1440
            }
            
            timeframe = timeframe_map.get(st.session_state.selected_timeframe, 15)
            symbol = st.session_state.selected_symbol
            
            # Try to get data from Redis
            key = f"mt5:ohlc:{symbol}:{timeframe}"
            data = self.redis_client.get(key)
            
            if data:
                data_dict = json.loads(data)
                df = pd.DataFrame({
                    'open': data_dict.get('open', []),
                    'high': data_dict.get('high', []),
                    'low': data_dict.get('low', []),
                    'close': data_dict.get('close', []),
                    'volume': data_dict.get('volume', data_dict.get('tick_volume', []))
                })
                
                if 'time' in data_dict:
                    df.index = pd.to_datetime(data_dict['time'])
                elif 'index' in data_dict:
                    df.index = pd.to_datetime(data_dict['index'])
                
                return df
            
        except Exception as e:
            st.error(f"Error loading data: {e}")
        
        # Return sample data if Redis is not available
        return self.generate_sample_data()
   
    def _generate_sample_data(self, symbol: str = "EURUSD") -> pd.DataFrame:
        """Generate sample OHLC data for testing with fixed pandas handling"""
        try:
            import numpy as np
            
            # Generate 100 candles of sample data
            periods = 100
            end_time = datetime.now().replace(second=0, microsecond=0)
            
            # Create time index with 15-minute intervals
            dates = pd.date_range(
                end=end_time, 
                periods=periods, 
                freq='15T'
            )
            
            # Start with a base price
            base_price = 1.1000 if symbol == "EURUSD" else 1.3000
            
            # Generate random walk for prices
            np.random.seed(42)  # For reproducible data
            changes = np.random.normal(0, 0.0001, periods)
            close_prices = base_price + np.cumsum(changes)
            
            # Generate realistic OHLC data
            data = []
            for i in range(periods):
                close = close_prices[i]
                
                # Generate open price (previous close + small gap)
                if i == 0:
                    open_price = base_price
                else:
                    gap = np.random.normal(0, 0.00005)
                    open_price = close_prices[i-1] + gap
                
                # Generate high and low
                high_offset = np.random.uniform(0.0001, 0.0005)
                low_offset = np.random.uniform(0.0001, 0.0005)
                
                high = max(open_price, close) + high_offset
                low = min(open_price, close) - low_offset
                
                # Generate volume
                volume = np.random.randint(100, 1000)
                
                data.append({
                    'open': round(open_price, 5),
                    'high': round(high, 5),
                    'low': round(low, 5),
                    'close': round(close, 5),
                    'volume': volume
                })
            
            # Create DataFrame properly
            df = pd.DataFrame(data, index=dates)
            
            # Ensure data integrity
            df['high'] = np.maximum(df['high'], np.maximum(df['open'], df['close']))
            df['low'] = np.minimum(df['low'], np.minimum(df['open'], df['close']))
            
            logger.debug(f"Generated sample data for {symbol}: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Error generating sample data: {e}")
            # Return minimal DataFrame if all else fails
            dates = pd.date_range(end=datetime.now(), periods=10, freq='15T')
            return pd.DataFrame({
                'open': [1.1000] * 10,
                'high': [1.1005] * 10,
                'low': [1.0995] * 10,
                'close': [1.1000] * 10,
                'volume': [500] * 10
            }, index=dates)
            
    def get_current_price(self) -> Optional[float]:
        """Get current price for selected symbol"""
        try:
            tick_data = self.redis_client.hgetall(f'mt5:tick:{st.session_state.selected_symbol}')
            if tick_data and 'bid' in tick_data:
                return float(tick_data['bid'])
        except:
            pass
        
        # Return sample price if Redis is not available
        return 1.0850 + np.random.randn() * 0.001
    
    def get_connection_status(self) -> bool:
        """Check connection status"""
        try:
            status = self.redis_client.hgetall('mt5:status')
            return status.get('connected') == 'true'
        except:
            return True  # Return True for demo
    
    def run(self):
        """Main dashboard loop"""
        # Render header
        self.render_header()
        
        # Sidebar controls
        self.render_indicator_controls()
        
        # Main content layout
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Trading chart
            self.render_tradingview_chart()
            
            # ML Prediction
            if st.session_state.show_indicators['ml_prediction']:
                self.render_ml_prediction()
        
        with col2:
            # Key levels
            self.render_levels_panel()
            
            # Fundamental analysis
            self.render_fundamental_analysis()
        
        # Auto-refresh every 5 seconds
        time.sleep(5)
        st.rerun()


# Main execution
if __name__ == "__main__":
    dashboard = EnhancedTradingDashboard()
    dashboard.run()