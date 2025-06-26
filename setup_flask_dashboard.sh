#!/bin/bash
# setup_flask_dashboard.sh

echo "Setting up Flask Trading Dashboard..."

# Create the updated dashboard_flask.py
cat > dashboard_flask.py << 'EOFLASK'
# dashboard_flask.py
"""
Flask-based Trading Dashboard Backend
Serves HTML dashboard and provides data API
"""

from flask import Flask, render_template_string, jsonify, request, send_file
from flask_cors import CORS
import redis
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)

# Redis connection
try:
    redis_client = redis.Redis(
        host=os.environ.get('REDIS_HOST', 'redis'),
        port=int(os.environ.get('REDIS_PORT', 6379)),
        decode_responses=True
    )
    redis_client.ping()  # Test connection
except:
    print("Warning: Redis connection failed, using demo mode")
    redis_client = None

@app.route('/')
def index():
    """Serve the main dashboard"""
    try:
        with open('trading_dashboard.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Dashboard file not found. Please ensure trading_dashboard.html is in the same directory.</h1>", 500

@app.route('/favicon.ico')
def favicon():
    """Return empty favicon to avoid 404 errors"""
    return '', 204

@app.route('/api/data')
def get_data():
    """API endpoint to get trading data"""
    try:
        symbol = request.args.get('symbol', 'EURUSD')
        timeframe = int(request.args.get('timeframe', 15))
        
        # Get OHLC data
        ohlc_data = get_ohlc_data(symbol, timeframe)
        
        # Calculate indicators
        levels = calculate_levels(ohlc_data)
        
        # Get current price
        current_price = get_current_price(symbol)
        
        # Get ML prediction (simulated for now)
        prediction = get_ml_prediction(symbol)
        
        # Get fundamental events
        fundamentals = get_fundamental_events()
        
        return jsonify({
            'success': True,
            'ohlc': ohlc_data,
            'levels': levels,
            'currentPrice': current_price,
            'prediction': prediction,
            'fundamentals': fundamentals
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def get_ohlc_data(symbol, timeframe):
    """Get OHLC data from Redis"""
    try:
        if redis_client:
            # Try to get data from Redis
            key = f"mt5:ohlc:{symbol}:{timeframe}"
            data = redis_client.get(key)
            
            if data:
                data_dict = json.loads(data)
                
                # Convert to list of dicts for frontend
                ohlc = []
                time_data = data_dict.get('time', [])
                open_data = data_dict.get('open', [])
                high_data = data_dict.get('high', [])
                low_data = data_dict.get('low', [])
                close_data = data_dict.get('close', [])
                volume_data = data_dict.get('volume', data_dict.get('tick_volume', []))
                
                for i in range(len(time_data)):
                    ohlc.append({
                        'time': time_data[i],
                        'open': float(open_data[i]) if i < len(open_data) else 0,
                        'high': float(high_data[i]) if i < len(high_data) else 0,
                        'low': float(low_data[i]) if i < len(low_data) else 0,
                        'close': float(close_data[i]) if i < len(close_data) else 0,
                        'volume': int(volume_data[i]) if i < len(volume_data) else 0
                    })
                
                return ohlc[-100:]  # Return last 100 candles
            
    except Exception as e:
        print(f"Error getting Redis data: {e}")
    
    # Return sample data if Redis fails
    return generate_sample_ohlc()

def calculate_levels(ohlc_data):
    """Calculate support and resistance levels"""
    if not ohlc_data:
        return {'resistance': [], 'support': []}
    
    # Convert to DataFrame for easier calculation
    df = pd.DataFrame(ohlc_data)
    
    levels = {'resistance': [], 'support': []}
    min_distance = 0.0010  # 10 pips
    
    # Simple level detection based on local highs/lows
    for i in range(10, len(df) - 10):
        # Check for resistance (local high)
        if df.iloc[i]['high'] == df.iloc[i-10:i+10]['high'].max():
            level = df.iloc[i]['high']
            
            # Check if not too close to existing levels
            too_close = False
            for existing in levels['resistance']:
                if abs(level - existing['price']) < min_distance:
                    too_close = True
                    break
            
            if not too_close:
                levels['resistance'].append({'price': level})
        
        # Check for support (local low)
        if df.iloc[i]['low'] == df.iloc[i-10:i+10]['low'].min():
            level = df.iloc[i]['low']
            
            too_close = False
            for existing in levels['support']:
                if abs(level - existing['price']) < min_distance:
                    too_close = True
                    break
            
            if not too_close:
                levels['support'].append({'price': level})
    
    # Sort and limit levels
    levels['resistance'].sort(key=lambda x: x['price'], reverse=True)
    levels['support'].sort(key=lambda x: x['price'])
    
    return {
        'resistance': levels['resistance'][:5],
        'support': levels['support'][:5]
    }

def get_current_price(symbol):
    """Get current price from Redis"""
    try:
        if redis_client:
            tick_data = redis_client.hgetall(f'mt5:tick:{symbol}')
            if tick_data and 'bid' in tick_data:
                return float(tick_data['bid'])
    except:
        pass
    
    # Return random price for demo
    return 1.0850 + np.random.randn() * 0.001

def get_ml_prediction(symbol):
    """Get ML prediction (simulated for now)"""
    # In production, this would call your ML model
    actions = ['BUY', 'SELL', 'HOLD']
    action = np.random.choice(actions, p=[0.4, 0.3, 0.3])
    confidence = np.random.uniform(60, 95)
    
    return {
        'action': action,
        'confidence': confidence
    }

def get_fundamental_events():
    """Get fundamental events (simulated for now)"""
    # In production, this would fetch from an economic calendar API
    return [
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

def generate_sample_ohlc():
    """Generate sample OHLC data for testing"""
    ohlc = []
    base_price = 1.0850
    
    for i in range(100):
        time = datetime.now() - timedelta(minutes=15 * (99 - i))
        open_price = base_price + np.random.randn() * 0.0005
        close_price = open_price + np.random.randn() * 0.0003
        high = max(open_price, close_price) + abs(np.random.randn() * 0.0002)
        low = min(open_price, close_price) - abs(np.random.randn() * 0.0002)
        volume = np.random.randint(1000, 5000)
        
        ohlc.append({
            'time': time.isoformat(),
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': volume
        })
        
        base_price = close_price
    
    return ohlc

@app.route('/api/status')
def get_status():
    """Get system status"""
    try:
        if redis_client:
            status = redis_client.hgetall('mt5:status')
            return jsonify({
                'connected': status.get('connected') == 'true',
                'account': status.get('account'),
                'server': status.get('server'),
                'balance': status.get('balance')
            })
    except:
        pass
    
    return jsonify({'connected': False})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
EOFLASK

echo "✓ Created dashboard_flask.py"

# Test if the HTML file exists
if [ ! -f "trading_dashboard.html" ]; then
    echo "⚠️  trading_dashboard.html not found. Please create it from the artifact."
    echo "   You can copy it from the HTML artifact provided earlier."
    exit 1
fi

echo "✓ Found trading_dashboard.html"

# Create updated Dockerfile
cat > Dockerfile.flask-dashboard << 'EODOCKERFILE'
# Dockerfile.flask-dashboard
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    flask==3.0.0 \
    flask-cors==4.0.0 \
    redis==5.0.1 \
    pandas==2.0.3 \
    numpy==1.24.3 \
    ta==0.11.0

# Copy application files
COPY dashboard_flask.py .
COPY trading_dashboard.html .

# Expose Flask port
EXPOSE 5000

# Run Flask
CMD ["python", "dashboard_flask.py"]
EODOCKERFILE

echo "✓ Created Dockerfile.flask-dashboard"

# Create docker-compose file
cat > docker-compose.flask.yml << 'EOCOMPOSE'
# docker-compose.flask.yml
services:
  # Direct connector (generates demo data)
  mt5-connector:
    build:
      context: .
      dockerfile: Dockerfile.direct
    container_name: mt5-connector
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - trading-network

  # Redis Service
  redis:
    image: redis:7-alpine
    container_name: trading-redis
    ports:
      - "6382:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - trading-network

  # Trading Backend Service
  trading-backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: trading-backend
    environment:
      - PYTHONUNBUFFERED=1
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
      - mt5-connector
    volumes:
      - ./trading_system:/app/trading_system
      - ./logs:/app/logs
    ports:
      - "8009:8000"
    restart: unless-stopped
    networks:
      - trading-network

  # Flask Dashboard Service
  flask-dashboard:
    build:
      context: .
      dockerfile: Dockerfile.flask-dashboard
    container_name: flask-dashboard
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    depends_on:
      - redis
      - mt5-connector
    ports:
      - "5000:5000"
    restart: unless-stopped
    networks:
      - trading-network

volumes:
  redis_data:

networks:
  trading-network:
    driver: bridge
EOCOMPOSE

echo "✓ Created docker-compose.flask.yml"

echo ""
echo "Setup complete! To run the Flask dashboard:"
echo ""
echo "1. Make sure trading_dashboard.html exists (copy from the HTML artifact)"
echo "2. Build and run:"
echo "   docker compose -f docker-compose.flask.yml build flask-dashboard"
echo "   docker compose -f docker-compose.flask.yml up -d"
echo ""
echo "3. Access the dashboard at: http://localhost:5000"
echo ""
echo "4. Check logs:"
echo "   docker logs flask-dashboard"
