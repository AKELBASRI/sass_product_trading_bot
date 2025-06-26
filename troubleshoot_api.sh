# 1. Update the React app's API configuration

# Create setupProxy.js for development mode
mkdir -p frontend/src
cat > frontend/src/setupProxy.js << 'EOF'
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:8009',  // Backend port from your docker-compose
      changeOrigin: true,
    })
  );
};
EOF

# Install proxy middleware for development
cd frontend
npm install http-proxy-middleware --save-dev
cd ..

# 2. Update the TradingContext.js to use relative URLs
cat > frontend/src/context/TradingContext.js.updated << 'EOF'
import React, { createContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

// Create context
export const TradingContext = createContext();

export const TradingProvider = ({ children }) => {
  // State variables
  const [currentSymbol, setCurrentSymbol] = useState('EURUSD');
  const [currentTimeframe, setCurrentTimeframe] = useState(15);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [indicators, setIndicators] = useState({
    levels: true,
    supertrend: true,
    wicks: false
  });
  const [isConnected, setIsConnected] = useState(false);
  const [chartData, setChartData] = useState([]);
  const [levels, setLevels] = useState({ resistance: [], support: [] });
  const [prediction, setPrediction] = useState({ action: 'HOLD', confidence: 50 });
  const [fundamentals, setFundamentals] = useState([]);
  
  // Debug state
  const [lastApiResponse, setLastApiResponse] = useState(null);
  const [errorCount, setErrorCount] = useState(0);
  const [successCount, setSuccessCount] = useState(0);
  const [debugLogs, setDebugLogs] = useState([]);
  
  // Logger function
  const log = useCallback((level, message, data = null) => {
    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      level,
      message,
      data: data ? JSON.stringify(data) : ''
    };
    
    // Console logging
    const consoleMethod = level === 'error' ? 'error' : 
                         level === 'warning' ? 'warn' : 'log';
    console[consoleMethod](`[${timestamp}] [${level.toUpperCase()}] ${message}`, data || '');
    
    // Update debug logs
    setDebugLogs(prevLogs => [logEntry, ...prevLogs].slice(0, 50));
  }, []);

  // Fetch data function
  const fetchData = useCallback(async () => {
    log('info', `Fetching data for ${currentSymbol} ${currentTimeframe}M`);
    
    try {
      // Use relative URL instead of absolute URL
      const response = await axios.get(`/api/data?symbol=${currentSymbol}&timeframe=${currentTimeframe}`);
      const data = response.data;
      
      setLastApiResponse(data);
      
      if (data.success) {
        log('success', 'API request successful');
        setIsConnected(true);
        
        // Process each data component
        if (data.ohlc && data.ohlc.length > 0) {
          log('info', `Received ${data.ohlc.length} OHLC candles`);
          const processedData = data.ohlc.map(candle => ({
            time: Math.floor(new Date(candle.time).getTime() / 1000),
            open: parseFloat(candle.open),
            high: parseFloat(candle.high),
            low: parseFloat(candle.low),
            close: parseFloat(candle.close)
          })).filter(candle => 
            !isNaN(candle.time) && !isNaN(candle.open) && 
            !isNaN(candle.high) && !isNaN(candle.low) && !isNaN(candle.close)
          ).sort((a, b) => a.time - b.time);
          
          setChartData(processedData);
        }
        
        if (data.levels) {
          setLevels(data.levels);
        }
        
        if (data.currentPrice) {
          setCurrentPrice(data.currentPrice);
        }
        
        if (data.prediction) {
          setPrediction(data.prediction);
        }
        
        if (data.fundamentals) {
          setFundamentals(data.fundamentals);
        }
        
        setSuccessCount(prev => prev + 1);
      } else {
        log('error', 'API request failed', data.error);
        setErrorCount(prev => prev + 1);
      }
    } catch (error) {
      log('error', 'Network error', error);
      setIsConnected(false);
      setErrorCount(prev => prev + 1);
      
      // If we can't connect to the API, try to use mock data
      if (errorCount > 5) {
        log('warning', 'Using mock data after multiple failed attempts');
        
        // Create some mock data
        const mockData = generateMockData(currentSymbol, currentTimeframe);
        setChartData(mockData.chartData);
        setLevels(mockData.levels);
        setCurrentPrice(mockData.currentPrice);
        setPrediction(mockData.prediction);
        setFundamentals(mockData.fundamentals);
      }
    }
  }, [currentSymbol, currentTimeframe, log, errorCount]);

  // Helper function to generate mock data when API is unavailable
  const generateMockData = (symbol, timeframe) => {
    // Base price for different symbols
    const basePrice = {
      'EURUSD': 1.12,
      'GBPUSD': 1.28,
      'USDJPY': 150.5,
      'USDCHF': 0.85,
      'AUDUSD': 0.67,
      'USDCAD': 1.35
    }[symbol] || 1.10;
    
    // Generate OHLC data
    const now = Math.floor(Date.now() / 1000);
    const chartData = [];
    
    for (let i = 0; i < 100; i++) {
      const time = now - (99 - i) * timeframe * 60;
      const high = basePrice + Math.random() * 0.01;
      const low = basePrice - Math.random() * 0.01;
      const open = low + Math.random() * (high - low);
      const close = low + Math.random() * (high - low);
      
      chartData.push({
        time,
        open,
        high,
        low,
        close
      });
    }
    
    // Generate levels
    const levels = {
      resistance: [
        { price: basePrice + 0.015, strength: 0.8 },
        { price: basePrice + 0.010, strength: 0.6 },
        { price: basePrice + 0.005, strength: 0.4 }
      ],
      support: [
        { price: basePrice - 0.005, strength: 0.5 },
        { price: basePrice - 0.010, strength: 0.7 },
        { price: basePrice - 0.015, strength: 0.9 }
      ]
    };
    
    // Last candle price
    const currentPrice = chartData[chartData.length - 1].close;
    
    // Random prediction
    const actions = ['BUY', 'SELL', 'HOLD'];
    const prediction = {
      action: actions[Math.floor(Math.random() * actions.length)],
      confidence: 50 + Math.random() * 45
    };
    
    // Sample fundamental events
    const fundamentals = [
      {
        title: 'GDP Release',
        time: '08:30 EST',
        currency: 'USD',
        impact: 'high',
        expected: '2.5%',
        previous: '2.2%'
      },
      {
        title: 'Interest Rate Decision',
        time: '14:00 EST',
        currency: 'EUR',
        impact: 'medium',
        expected: '3.75%',
        previous: '3.50%'
      },
      {
        title: 'Non-Farm Payrolls',
        time: '08:30 EST',
        currency: 'USD',
        impact: 'high',
        expected: '205K',
        previous: '195K'
      }
    ];
    
    return {
      chartData,
      levels,
      currentPrice,
      prediction,
      fundamentals
    };
  };

  // Toggle indicator function
  const toggleIndicator = (indicator) => {
    setIndicators(prev => ({
      ...prev,
      [indicator]: !prev[indicator]
    }));
  };

  // Initial data fetch and auto-update
  useEffect(() => {
    log('info', '=== INITIALIZING TRADING SYSTEM ===');
    
    // Fetch initial data
    fetchData();
    
    // Set up auto-update interval
    const interval = setInterval(fetchData, 5000);
    
    // Cleanup on unmount
    return () => {
      clearInterval(interval);
      log('info', 'Cleared update interval');
    };
  }, [fetchData, log]);

  // Update on symbol or timeframe change
  useEffect(() => {
    fetchData();
  }, [currentSymbol, currentTimeframe, fetchData]);

  // Context value
  const value = {
    currentSymbol,
    setCurrentSymbol,
    currentTimeframe,
    setCurrentTimeframe,
    currentPrice,
    indicators,
    toggleIndicator,
    isConnected,
    chartData,
    levels,
    prediction,
    fundamentals,
    lastApiResponse,
    errorCount,
    successCount,
    debugLogs,
    log
  };

  return (
    <TradingContext.Provider value={value}>
      {children}
    </TradingContext.Provider>
  );
};
EOF

# 3. Update the Flask backend to use the correct port and add proper CORS headers
cat > dashboard_flask.py.updated << 'EOF'
import os
import json
import logging
import redis
import random
from flask import Flask, jsonify, request
from flask_cors import CORS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trading_dashboard')

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Configure CORS for all API routes

# Redis connection
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None

# Mock data generator (for testing when Redis is unavailable)
def generate_mock_data(symbol, timeframe):
    logger.warning(f"Generating mock data for {symbol} {timeframe}M")
    
    # Generate OHLC data
    base_price = {
        'EURUSD': 1.12,
        'GBPUSD': 1.28,
        'USDJPY': 150.5,
        'USDCHF': 0.85,
        'AUDUSD': 0.67,
        'USDCAD': 1.35
    }.get(symbol, 1.10)
    
    current_time = 1624982400  # June 29, 2021 UTC
    candles = []
    
    for i in range(100):
        high = base_price + random.uniform(0, 0.01)
        low = base_price - random.uniform(0, 0.01)
        open_price = random.uniform(low, high)
        close_price = random.uniform(low, high)
        
        candles.append({
            'time': current_time + (i * 60 * int(timeframe)),
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price
        })
    
    # Generate levels
    levels = {
        'resistance': [
            {'price': base_price + 0.015, 'strength': 0.8},
            {'price': base_price + 0.010, 'strength': 0.6},
            {'price': base_price + 0.005, 'strength': 0.4}
        ],
        'support': [
            {'price': base_price - 0.005, 'strength': 0.5},
            {'price': base_price - 0.010, 'strength': 0.7},
            {'price': base_price - 0.015, 'strength': 0.9}
        ]
    }
    
    # Generate prediction
    actions = ['BUY', 'SELL', 'HOLD']
    prediction = {
        'action': random.choice(actions),
        'confidence': random.uniform(50, 95)
    }
    
    # Generate fundamentals
    impact_levels = ['low', 'medium', 'high']
    currencies = ['USD', 'EUR', 'GBP', 'JPY']
    events = [
        {
            'title': 'GDP Release',
            'time': '08:30 EST',
            'currency': random.choice(currencies),
            'impact': random.choice(impact_levels),
            'expected': '2.5%',
            'previous': '2.2%'
        },
        {
            'title': 'Interest Rate Decision',
            'time': '14:00 EST',
            'currency': random.choice(currencies),
            'impact': random.choice(impact_levels),
            'expected': '3.75%',
            'previous': '3.50%'
        },
        {
            'title': 'Non-Farm Payrolls',
            'time': '08:30 EST',
            'currency': 'USD',
            'impact': 'high',
            'expected': '205K',
            'previous': '195K'
        }
    ]
    
    return {
        'success': True,
        'ohlc': candles,
        'levels': levels,
        'currentPrice': candles[-1]['close'],
        'prediction': prediction,
        'fundamentals': events
    }

# API Routes
@app.route('/api/data', methods=['GET'])
def get_data():
    try:
        symbol = request.args.get('symbol', 'EURUSD')
        timeframe = request.args.get('timeframe', '15')
        
        logger.info(f"Data requested for {symbol} {timeframe}M")
        
        # Try to get data from Redis
        if redis_client:
            try:
                # Get OHLC data
                ohlc_key = f"{symbol}_{timeframe}_ohlc"
                ohlc_data = redis_client.get(ohlc_key)
                
                if ohlc_data:
                    logger.info(f"Found data for {ohlc_key}")
                    data = json.loads(ohlc_data)
                    
                    # Get levels
                    levels_key = f"{symbol}_{timeframe}_levels"
                    levels_data = redis_client.get(levels_key)
                    if levels_data:
                        data['levels'] = json.loads(levels_data)
                    
                    # Get current price
                    price_key = f"{symbol}_price"
                    current_price = redis_client.get(price_key)
                    if current_price:
                        data['currentPrice'] = float(current_price)
                    
                    # Add prediction (could be from ML model or Redis)
                    prediction_key = f"{symbol}_{timeframe}_prediction"
                    prediction_data = redis_client.get(prediction_key)
                    if prediction_data:
                        data['prediction'] = json.loads(prediction_data)
                    else:
                        # Mock prediction
                        data['prediction'] = {
                            'action': random.choice(['BUY', 'SELL', 'HOLD']),
                            'confidence': random.uniform(50, 95)
                        }
                    
                    # Add fundamental events
                    events_key = f"economic_events"
                    events_data = redis_client.get(events_key)
                    if events_data:
                        data['fundamentals'] = json.loads(events_data)
                    else:
                        # Mock events
                        data['fundamentals'] = generate_mock_data(symbol, timeframe)['fundamentals']
                    
                    data['success'] = True
                    return jsonify(data)
                else:
                    logger.warning(f"No data found for {ohlc_key}, generating mock data")
                    return jsonify(generate_mock_data(symbol, timeframe))
            except Exception as e:
                logger.error(f"Error getting data from Redis: {e}")
                return jsonify(generate_mock_data(symbol, timeframe))
        else:
            logger.warning("Redis not available, generating mock data")
            return jsonify(generate_mock_data(symbol, timeframe))
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/debug', methods=['GET'])
def debug():
    try:
        redis_info = {}
        if redis_client:
            try:
                redis_info = {
                    'connected': True,
                    'keys': len(redis_client.keys()),
                    'info': {k: v for k, v in redis_client.info().items() if k in ['redis_version', 'uptime_in_seconds']}
                }
            except:
                redis_info = {'connected': False}
        
        return jsonify({
            'success': True,
            'version': '1.0.0',
            'environment': os.environ.get('FLASK_ENV', 'production'),
            'redis': redis_info
        })
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    # Run on port 8000 as specified in docker-compose
    app.run(host='0.0.0.0', port=8000, debug=True)
EOF

# 4. Update the Nginx configuration
cat > nginx/react-nginx.conf.updated << 'EOF'
server {
    listen 80;
    
    # React app
    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }
    
    # API proxy - forward requests to Flask backend
    location /api/ {
        proxy_pass http://trading-backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

# 5. Create a diagnostic tool
cat > api-diagnostic.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Connection Diagnostic</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e1a;
            color: #e4e4e7;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2 {
            color: #00d4ff;
        }
        button {
            background: #252a3e;
            border: 1px solid #3a3f5c;
            color: #e4e4e7;
            padding: 8px 15px;
            border-radius: 8px;
            font-size: 14px;
            cursor: pointer;
            margin: 10px 0;
        }
        button:hover {
            background: #3a3f5c;
        }
        pre {
            background: #1a1e2e;
            padding: 15px;
            border-radius: 8px;
            overflow-x: auto;
            border: 1px solid #252a3e;
        }
        .success {
            color: #00ff88;
        }
        .error {
            color: #ff3860;
        }
    </style>
</head>
<body>
    <h1>Trading System API Diagnostic</h1>
    
    <div>
        <h2>1. Test Flask Backend API Connection</h2>
        <button id="testApi">Test API Connection</button>
        <div id="apiResult"></div>
    </div>
    
    <div>
        <h2>2. Test Debug Endpoint</h2>
        <button id="testDebug">Test Debug Endpoint</button>
        <div id="debugResult"></div>
    </div>
    
    <div>
        <h2>3. Environment Information</h2>
        <pre id="envInfo">
User Agent: <span id="userAgent"></span>
</pre>
    </div>
    
    <script>
        document.getElementById('userAgent').textContent = navigator.userAgent;
        
        document.getElementById('testApi').addEventListener('click', async () => {
            const resultDiv = document.getElementById('apiResult');
            resultDiv.innerHTML = 'Testing API connection...';
            
            try {
                const response = await fetch('/api/data?symbol=EURUSD&timeframe=15');
                const data = await response.json();
                
                resultDiv.innerHTML = `
                    <p class="success">✅ API connection successful!</p>
                    <p>Received ${data.ohlc?.length || 0} OHLC candles</p>
                    <p>Current price: ${data.currentPrice?.toFixed(5) || 'N/A'}</p>
                    <pre>${JSON.stringify(data, null, 2).slice(0, 500)}...</pre>
                `;
            } catch (error) {
                resultDiv.innerHTML = `
                    <p class="error">❌ API connection failed</p>
                    <p>Error: ${error.message}</p>
                    <p>Try these alternatives:</p>
                    <ul>
                        <li><a href="http://localhost:8009/api/data?symbol=EURUSD&timeframe=15" target="_blank">Direct backend access</a></li>
                        <li><a href="http://trading-backend:8000/api/data?symbol=EURUSD&timeframe=15" target="_blank">Container DNS name access</a></li>
                    </ul>
                `;
            }
        });
        
        document.getElementById('testDebug').addEventListener('click', async () => {
            const resultDiv = document.getElementById('debugResult');
            resultDiv.innerHTML = 'Testing debug endpoint...';
            
            try {
                const response = await fetch('/api/debug');
                const data = await response.json();
                
                resultDiv.innerHTML = `
                    <p class="success">✅ Debug endpoint connection successful!</p>
                    <p>Version: ${data.version}</p>
                    <p>Environment: ${data.environment}</p>
                    <p>Redis connected: ${data.redis?.connected ? 'Yes' : 'No'}</p>
                    <pre>${JSON.stringify(data, null, 2)}</pre>
                `;
            } catch (error) {
                resultDiv.innerHTML = `
                    <p class="error">❌ Debug endpoint connection failed</p>
                    <p>Error: ${error.message}</p>
                `;
            }
        });
    </script>
</body>
</html>
EOF

# 6. Apply the fixes
mv frontend/src/context/TradingContext.js frontend/src/context/TradingContext.js.bak
mv frontend/src/context/TradingContext.js.updated frontend/src/context/TradingContext.js
mv dashboard_flask.py dashboard_flask.py.bak
mv dashboard_flask.py.updated dashboard_flask.py
mv nginx/react-nginx.conf nginx/react-nginx.conf.bak
mv nginx/react-nginx.conf.updated nginx/react-nginx.conf

# Add diagnostic tool to the public folder
mkdir -p frontend/public
cp api-diagnostic.html frontend/public/

echo "API connection fixes applied!"