#!/bin/bash

set -e

echo "🚀 Setting up Trading Dashboard..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_HOST="168.231.87.87"
BACKEND_PORT="8009"
FRONTEND_PORT="3000"
PROJECT_NAME="trading-dashboard"

echo -e "${BLUE}📋 Configuration:${NC}"
echo -e "  Backend: http://${BACKEND_HOST}:${BACKEND_PORT}"
echo -e "  Frontend: http://localhost:${FRONTEND_PORT}"
echo -e "  Project: ${PROJECT_NAME}"
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed. Please install Node.js first.${NC}"
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm is not installed. Please install npm first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Node.js and npm are installed${NC}"

# Create project directory
echo -e "${YELLOW}📁 Creating project directory...${NC}"
rm -rf $PROJECT_NAME
mkdir -p $PROJECT_NAME
cd $PROJECT_NAME

# Initialize React app
echo -e "${YELLOW}⚛️ Creating React application...${NC}"
npx create-react-app frontend --template typescript
cd frontend

# Install dependencies
echo -e "${YELLOW}📦 Installing dependencies...${NC}"
npm install lightweight-charts axios lucide-react tailwindcss @types/node

# Setup Tailwind CSS
echo -e "${YELLOW}🎨 Setting up Tailwind CSS...${NC}"
npx tailwindcss init -p

# Create Tailwind config
cat > tailwind.config.js << 'EOF'
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'trading-dark': '#1a1a1a',
        'trading-card': '#2a2a2a',
        'trading-border': '#3a3a3a',
        'trading-green': '#00d4aa',
        'trading-red': '#ff6b6b',
      }
    },
  },
  plugins: [],
}
EOF

# Update index.css with Tailwind
cat > src/index.css << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: #1a1a1a;
  color: white;
}

code {
  font-family: source-code-pro, Menlo, Monaco, Consolas, 'Courier New',
    monospace;
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #2a2a2a;
}

::-webkit-scrollbar-thumb {
  background: #3a3a3a;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #4a4a4a;
}
EOF

# Create API service
mkdir -p src/services
cat > src/services/api.ts << EOF
import axios from 'axios';

const API_BASE_URL = 'http://${BACKEND_HOST}:${BACKEND_PORT}';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface CandleData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OHLCResponse {
  symbol: string;
  timeframe: string;
  data: CandleData[];
  count: number;
  error?: string;
}

export interface SystemStatus {
  running: boolean;
  last_update: string;
  current_time: string;
  error?: string;
  redis_connected: boolean;
  mt5_connected: boolean;
  active_symbols: string[];
}

export interface SymbolsResponse {
  symbols: string[];
  count: number;
}

class TradingAPI {
  async getStatus(): Promise<SystemStatus> {
    const response = await api.get('/status');
    return response.data;
  }

  async getSymbols(): Promise<SymbolsResponse> {
    const response = await api.get('/symbols');
    return response.data;
  }

  async getOHLCData(symbol: string, timeframe: string = '15', limit: number = 100): Promise<OHLCResponse> {
    const response = await api.get(\`/ohlc/\${symbol}\`, {
      params: { timeframe, limit }
    });
    return response.data;
  }

  async startSystem(): Promise<{ message: string }> {
    const response = await api.post('/start');
    return response.data;
  }

  async stopSystem(): Promise<{ message: string }> {
    const response = await api.post('/stop');
    return response.data;
  }

  async getHealth(): Promise<any> {
    const response = await api.get('/health');
    return response.data;
  }
}

export const tradingAPI = new TradingAPI();
export default api;
EOF

# Create TradingChart component
mkdir -p src/components
cat > src/components/TradingChart.tsx << 'EOF'
import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, Time } from 'lightweight-charts';
import { CandleData } from '../services/api';

interface TradingChartProps {
  data: CandleData[];
  symbol: string;
  timeframe: string;
}

const TradingChart: React.FC<TradingChartProps> = ({ data, symbol, timeframe }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const [chartReady, setChartReady] = useState(false);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 500,
      layout: {
        background: { color: '#1a1a1a' },
        textColor: '#ffffff',
      },
      grid: {
        vertLines: { color: '#2a2a2a' },
        horzLines: { color: '#2a2a2a' },
      },
      timeScale: {
        borderColor: '#3a3a3a',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#3a3a3a',
      },
      crosshair: {
        mode: 1,
      },
    });

    // Add candlestick series
    const series = chart.addCandlestickSeries({
      upColor: '#00d4aa',
      downColor: '#ff6b6b',
      borderUpColor: '#00d4aa',
      borderDownColor: '#ff6b6b',
      wickUpColor: '#00d4aa',
      wickDownColor: '#ff6b6b',
    });

    chartRef.current = chart;
    seriesRef.current = series;
    setChartReady(true);

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chart) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chart) {
        chart.remove();
      }
    };
  }, []);

  useEffect(() => {
    if (!chartReady || !seriesRef.current || !data || data.length === 0) return;

    // Convert data to TradingView format
    const chartData: CandlestickData[] = data.map((candle) => ({
      time: (new Date(candle.timestamp).getTime() / 1000) as Time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }));

    // Sort by time
    chartData.sort((a, b) => (a.time as number) - (b.time as number));

    seriesRef.current.setData(chartData);
    
    // Fit content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [data, chartReady]);

  return (
    <div className="w-full">
      <div className="mb-4 p-4 bg-trading-card rounded-lg border border-trading-border">
        <h2 className="text-xl font-bold text-white mb-2">
          {symbol} - {timeframe}min Chart
        </h2>
        <div className="flex gap-4 text-sm text-gray-300">
          <span>Data points: {data.length}</span>
          {data.length > 0 && (
            <>
              <span>Latest: ${data[data.length - 1]?.close.toFixed(5)}</span>
              <span className={`${
                data.length > 1 && data[data.length - 1]?.close > data[data.length - 2]?.close 
                  ? 'text-trading-green' 
                  : 'text-trading-red'
              }`}>
                {data.length > 1 && (
                  (data[data.length - 1]?.close - data[data.length - 2]?.close).toFixed(5)
                )}
              </span>
            </>
          )}
        </div>
      </div>
      <div 
        ref={chartContainerRef} 
        className="bg-trading-dark rounded-lg border border-trading-border"
        style={{ width: '100%', height: '500px' }}
      />
    </div>
  );
};

export default TradingChart;
EOF

# Create StatusIndicator component
cat > src/components/StatusIndicator.tsx << 'EOF'
import React from 'react';
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';

interface StatusIndicatorProps {
  connected: boolean;
  label: string;
  details?: string;
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({ connected, label, details }) => {
  return (
    <div className="flex items-center gap-2 p-2 rounded-lg bg-trading-card border border-trading-border">
      {connected ? (
        <CheckCircle className="w-5 h-5 text-trading-green" />
      ) : (
        <XCircle className="w-5 h-5 text-trading-red" />
      )}
      <div className="flex-1">
        <span className="text-white font-medium">{label}</span>
        {details && (
          <div className="text-xs text-gray-400">{details}</div>
        )}
      </div>
    </div>
  );
};

export default StatusIndicator;
EOF

# Create SymbolSelector component
cat > src/components/SymbolSelector.tsx << 'EOF'
import React from 'react';

interface SymbolSelectorProps {
  symbols: string[];
  selectedSymbol: string;
  onSymbolChange: (symbol: string) => void;
  selectedTimeframe: string;
  onTimeframeChange: (timeframe: string) => void;
  onRefresh: () => void;
  loading: boolean;
}

const timeframes = [
  { value: '1', label: '1min' },
  { value: '5', label: '5min' },
  { value: '15', label: '15min' },
  { value: '30', label: '30min' },
  { value: '60', label: '1hour' },
  { value: '240', label: '4hour' },
  { value: '1440', label: '1day' },
];

const SymbolSelector: React.FC<SymbolSelectorProps> = ({
  symbols,
  selectedSymbol,
  onSymbolChange,
  selectedTimeframe,
  onTimeframeChange,
  onRefresh,
  loading
}) => {
  return (
    <div className="bg-trading-card p-4 rounded-lg border border-trading-border">
      <h3 className="text-lg font-semibold text-white mb-4">Trading Controls</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Symbol Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Symbol
          </label>
          <select
            value={selectedSymbol}
            onChange={(e) => onSymbolChange(e.target.value)}
            className="w-full p-2 bg-trading-dark border border-trading-border rounded-md text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          >
            {symbols.map((symbol) => (
              <option key={symbol} value={symbol}>
                {symbol}
              </option>
            ))}
          </select>
        </div>

        {/* Timeframe Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Timeframe
          </label>
          <select
            value={selectedTimeframe}
            onChange={(e) => onTimeframeChange(e.target.value)}
            className="w-full p-2 bg-trading-dark border border-trading-border rounded-md text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          >
            {timeframes.map((tf) => (
              <option key={tf.value} value={tf.value}>
                {tf.label}
              </option>
            ))}
          </select>
        </div>

        {/* Refresh Button */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Actions
          </label>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="w-full p-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-md transition-colors"
          >
            {loading ? 'Loading...' : 'Refresh Data'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SymbolSelector;
EOF

# Create main App component
cat > src/App.tsx << 'EOF'
import React, { useState, useEffect, useCallback } from 'react';
import { Activity, Database, Server, RefreshCw, AlertTriangle } from 'lucide-react';
import TradingChart from './components/TradingChart';
import StatusIndicator from './components/StatusIndicator';
import SymbolSelector from './components/SymbolSelector';
import { tradingAPI, CandleData, SystemStatus } from './services/api';

function App() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>('EURUSD');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('15');
  const [chartData, setChartData] = useState<CandleData[]>([]);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // Fetch system status
  const fetchStatus = useCallback(async () => {
    try {
      const statusData = await tradingAPI.getStatus();
      setStatus(statusData);
    } catch (err) {
      console.error('Failed to fetch status:', err);
      setError('Failed to connect to trading backend');
    }
  }, []);

  // Fetch available symbols
  const fetchSymbols = useCallback(async () => {
    try {
      const symbolsData = await tradingAPI.getSymbols();
      setSymbols(symbolsData.symbols);
      if (symbolsData.symbols.length > 0 && !symbolsData.symbols.includes(selectedSymbol)) {
        setSelectedSymbol(symbolsData.symbols[0]);
      }
    } catch (err) {
      console.error('Failed to fetch symbols:', err);
      setError('Failed to fetch symbols');
    }
  }, [selectedSymbol]);

  // Fetch chart data
  const fetchChartData = useCallback(async () => {
    if (!selectedSymbol) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const ohlcData = await tradingAPI.getOHLCData(selectedSymbol, selectedTimeframe, 200);
      
      if (ohlcData.error) {
        setError(ohlcData.error);
        setChartData([]);
      } else {
        setChartData(ohlcData.data);
        setLastUpdate(new Date());
      }
    } catch (err: any) {
      console.error('Failed to fetch chart data:', err);
      setError(err.response?.data?.detail || 'Failed to fetch chart data');
      setChartData([]);
    } finally {
      setLoading(false);
    }
  }, [selectedSymbol, selectedTimeframe]);

  // Initial data fetch
  useEffect(() => {
    fetchStatus();
    fetchSymbols();
  }, [fetchStatus, fetchSymbols]);

  // Fetch chart data when symbol or timeframe changes
  useEffect(() => {
    if (selectedSymbol) {
      fetchChartData();
    }
  }, [fetchChartData]);

  // Auto-refresh status every 30 seconds
  useEffect(() => {
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleRefresh = () => {
    fetchChartData();
    fetchStatus();
  };

  const handleStartSystem = async () => {
    try {
      await tradingAPI.startSystem();
      await fetchStatus();
    } catch (err) {
      console.error('Failed to start system:', err);
    }
  };

  const handleStopSystem = async () => {
    try {
      await tradingAPI.stopSystem();
      await fetchStatus();
    } catch (err) {
      console.error('Failed to stop system:', err);
    }
  };

  return (
    <div className="min-h-screen bg-trading-dark text-white">
      {/* Header */}
      <header className="bg-trading-card border-b border-trading-border p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-8 h-8 text-blue-500" />
            <h1 className="text-2xl font-bold">Trading Dashboard</h1>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="p-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded-md transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            
            {status && (
              <div className="flex gap-2">
                {status.running ? (
                  <button
                    onClick={handleStopSystem}
                    className="px-3 py-1 bg-red-600 hover:bg-red-700 text-sm rounded-md transition-colors"
                  >
                    Stop System
                  </button>
                ) : (
                  <button
                    onClick={handleStartSystem}
                    className="px-3 py-1 bg-green-600 hover:bg-green-700 text-sm rounded-md transition-colors"
                  >
                    Start System
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto p-4">
        {/* Error Alert */}
        {error && (
          <div className="mb-4 p-4 bg-red-900/50 border border-red-700 rounded-lg flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <span className="text-red-100">{error}</span>
          </div>
        )}

        {/* Status Section */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <StatusIndicator
            connected={status?.redis_connected || false}
            label="Redis Database"
            details={status?.redis_connected ? 'Connected' : 'Disconnected'}
          />
          <StatusIndicator
            connected={status?.mt5_connected || false}
            label="MT5 Data Feed"
            details={status?.mt5_connected ? `${status.active_symbols.length} symbols` : 'No data'}
          />
          <StatusIndicator
            connected={status?.running || false}
            label="Trading System"
            details={status?.running ? 'Running' : 'Stopped'}
          />
        </div>

        {/* Controls */}
        <div className="mb-6">
          <SymbolSelector
            symbols={symbols}
            selectedSymbol={selectedSymbol}
            onSymbolChange={setSelectedSymbol}
            selectedTimeframe={selectedTimeframe}
            onTimeframeChange={setSelectedTimeframe}
            onRefresh={handleRefresh}
            loading={loading}
          />
        </div>

        {/* Chart Section */}
        <div className="mb-6">
          {chartData.length > 0 ? (
            <TradingChart 
              data={chartData} 
              symbol={selectedSymbol} 
              timeframe={selectedTimeframe}
            />
          ) : (
            <div className="bg-trading-card rounded-lg border border-trading-border p-8 text-center">
              <Database className="w-16 h-16 text-gray-500 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-300 mb-2">No Chart Data Available</h3>
              <p className="text-gray-500 mb-4">
                {loading ? 'Loading chart data...' : 'Select a symbol and timeframe to view chart data.'}
              </p>
              {!loading && (
                <button
                  onClick={handleRefresh}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors"
                >
                  Load Data
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer Info */}
        <footer className="bg-trading-card rounded-lg border border-trading-border p-4">
          <div className="flex items-center justify-between text-sm text-gray-400">
            <div className="flex items-center gap-4">
              <span>Backend: 168.231.87.87:8009</span>
              <span>•</span>
              <span>Symbols: {symbols.length}</span>
              <span>•</span>
              <span>Last Update: {lastUpdate.toLocaleTimeString()}</span>
            </div>
            
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4" />
              <span>Trading Dashboard v1.0</span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default App;
EOF

# Update package.json to set homepage
echo -e "${YELLOW}📝 Updating package.json...${NC}"
npm pkg set homepage="."

# Create build script
cat > ../build-and-serve.sh << 'EOF'
#!/bin/bash

echo "🔨 Building React app..."
cd frontend
npm run build

echo "🚀 Starting development server..."
npm start
EOF

chmod +x ../build-and-serve.sh

# Create production build script
cat > ../build-production.sh << 'EOF'
#!/bin/bash

echo "🔨 Building React app for production..."
cd frontend
npm run build

echo "📦 Production build complete!"
echo "Files are in frontend/build/"
echo ""
echo "To serve the production build:"
echo "  npm install -g serve"
echo "  serve -s build -l 3000"
EOF

chmod +x ../build-production.sh

# Create start script
cat > ../start-dashboard.sh << 'EOF'
#!/bin/bash

echo "🚀 Starting Trading Dashboard..."
cd frontend
npm start
EOF

chmod +x ../start-dashboard.sh

# Go back to project root
cd ..

echo ""
echo -e "${GREEN}✅ Trading Dashboard setup complete!${NC}"
echo ""
echo -e "${BLUE}📁 Project structure:${NC}"
echo "  $PROJECT_NAME/"
echo "  ├── frontend/                 # React TypeScript app"
echo "  ├── build-and-serve.sh       # Build and serve script"
echo "  ├── build-production.sh      # Production build script"
echo "  └── start-dashboard.sh       # Start development server"
echo ""
echo -e "${BLUE}🎯 Next steps:${NC}"
echo "  1. Start the dashboard:"
echo "     cd $PROJECT_NAME && ./start-dashboard.sh"
echo ""
echo "  2. Open your browser:"
echo "     http://localhost:3000"
echo ""
echo -e "${BLUE}🔧 Backend integration:${NC}"
echo "  - Backend URL: http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "  - Make sure your backend is running and accessible"
echo "  - CORS is configured for all origins"
echo ""
echo -e "${BLUE}🎨 Features included:${NC}"
echo "  ✅ TradingView Lightweight Charts"
echo "  ✅ Symbol and timeframe selection"
echo "  ✅ Real-time status monitoring"
echo "  ✅ System start/stop controls"
echo "  ✅ Dark trading theme"
echo "  ✅ Responsive design"
echo "  ✅ Error handling"
echo "  ✅ Auto-refresh capabilities"
echo ""
echo -e "${YELLOW}⚠️  Make sure your backend is running on ${BACKEND_HOST}:${BACKEND_PORT}${NC}"

# Create README
cat > README.md << EOF
# Trading Dashboard

A modern React TypeScript dashboard for trading data visualization using TradingView Lightweight Charts.

## Features

- 📈 **Real-time Charts**: TradingView Lightweight Charts integration
- 🔄 **Live Data**: Connect to your trading backend
- 🎛️ **Controls**: Symbol and timeframe selection
- 📊 **Status Monitoring**: System health indicators
- 🎨 **Modern UI**: Dark theme optimized for trading
- 📱 **Responsive**: Works on desktop and mobile

## Quick Start

1. **Start the dashboard:**
   \`\`\`bash
   ./start-dashboard.sh
   \`\`\`

2. **Open your browser:**
   \`\`\`
   http://localhost:3000
   \`\`\`

## Backend Configuration

- **Backend URL**: http://${BACKEND_HOST}:${BACKEND_PORT}
- **Required endpoints**: /status, /symbols, /ohlc/{symbol}
- **CORS**: Must allow requests from localhost:3000

## Available Scripts

- \`./start-dashboard.sh\` - Start development server
- \`./build-production.sh\` - Build for production
- \`./build-and-serve.sh\` - Build and serve

## Supported Timeframes

- 1min, 5min, 15min, 30min
- 1hour, 4hour, 1day

## Technology Stack

- React 18 with TypeScript
- TradingView Lightweight Charts
- Tailwind CSS
- Axios for API calls
- Lucide React icons

## Backend Requirements

Your backend should provide these endpoints:

- \`GET /status\` - System status
- \`GET /symbols\` - Available symbols
- \`GET /ohlc/{symbol}?timeframe=15&limit=100\` - OHLC data
- \`POST /start\` - Start system
- \`POST /stop\` - Stop system

EOF

echo -e "${GREEN}🎉 Setup completed successfully!${NC}"
echo -e "${YELLOW}Run: cd $PROJECT_NAME && ./start-dashboard.sh${NC}"