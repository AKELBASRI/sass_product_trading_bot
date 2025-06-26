#!/bin/bash
# docker-entrypoint-mt5.sh

echo "Starting MT5 Linux container..."

# Set up display environment
export DISPLAY=:99
export QT_QPA_PLATFORM=offscreen

# Start Xvfb
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
sleep 2

# Start VNC if enabled
if [ "${ENABLE_VNC}" = "true" ]; then
    echo "Starting VNC server..."
    x11vnc -display :99 -bg -nopw -listen 0.0.0.0 -rfbport 5900 -forever -xkb -quiet &
    VNC_PID=$!
    echo "VNC server started on port 5900"
fi

# Create logs directory
mkdir -p /app/logs

# Create the mt5linux server script
cat > /app/start_mt5linux_server.py << 'EOF'
#!/usr/bin/env python3
import os
import sys
import time
import logging

os.environ['DISPLAY'] = ':99'
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Just importing mt5linux starts the server
    import mt5linux
    logger.info("mt5linux server started on port 18812")
    # Keep process alive
    while True:
        time.sleep(60)
except Exception as e:
    logger.error(f"Failed to start mt5linux: {e}")
    sys.exit(1)
EOF

# Start mt5linux server
echo "Starting mt5linux server..."
python3 /app/start_mt5linux_server.py > /app/logs/mt5linux.log 2>&1 &
MT5LINUX_PID=$!
echo "mt5linux started with PID: $MT5LINUX_PID"

# Wait for mt5linux to initialize
sleep 10

# Check if mt5linux is still running
if kill -0 $MT5LINUX_PID 2>/dev/null; then
    echo "mt5linux server is running"
else
    echo "ERROR: mt5linux failed to start. Check logs:"
    cat /app/logs/mt5linux.log
    exit 1
fi

# Start MT5 connector
echo "Starting MT5 connector..."
python3 /app/mt5_connector_enhanced.py > /app/logs/connector.log 2>&1 &
CONNECTOR_PID=$!
echo "Connector started with PID: $CONNECTOR_PID"

# Function to handle shutdown
cleanup() {
    echo "Shutting down services..."
    [ ! -z "$CONNECTOR_PID" ] && kill $CONNECTOR_PID 2>/dev/null
    [ ! -z "$MT5LINUX_PID" ] && kill $MT5LINUX_PID 2>/dev/null
    [ ! -z "$VNC_PID" ] && kill $VNC_PID 2>/dev/null
    [ ! -z "$XVFB_PID" ] && kill $XVFB_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Display status
echo "============================================"
echo "MT5 Linux Container Status:"
echo "mt5linux PID: $MT5LINUX_PID"
echo "Connector PID: $CONNECTOR_PID"
echo "mt5linux Port: 18812"
echo "VNC Port: 5900 (if enabled)"
echo "Display: $DISPLAY"
echo "============================================"
echo "Container is running. Press Ctrl+C to stop."
echo "Logs are available in /app/logs/"
echo "============================================"

# Simple monitoring loop
while true; do
    # Check processes every 30 seconds
    sleep 30
    
    # Check mt5linux
    if ! kill -0 $MT5LINUX_PID 2>/dev/null; then
        echo "WARNING: mt5linux process died!"
        tail -10 /app/logs/mt5linux.log
    fi
    
    # Check connector
    if ! kill -0 $CONNECTOR_PID 2>/dev/null; then
        echo "WARNING: Connector process died!"
        tail -10 /app/logs/connector.log
    fi
done