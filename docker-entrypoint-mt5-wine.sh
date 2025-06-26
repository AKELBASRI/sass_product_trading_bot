#!/bin/bash
# docker-entrypoint-mt5-wine.sh
# Entrypoint that starts MT5 in Wine and then your connector

echo "Starting MT5 Wine Container with Enhanced Connector..."

# Start the base gmag11 services first
# This includes Xvfb, Wine, MT5, and the RPyC server
/kasminit &
KASM_PID=$!

echo "Waiting for Wine and MT5 to initialize..."
# Wait for RPyC server to be available
MAX_WAIT=300  # 5 minutes max wait
WAITED=0

while ! nc -z localhost 8001; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "ERROR: RPyC server did not start within $MAX_WAIT seconds"
        exit 1
    fi
    echo "Waiting for RPyC server on port 8001... ($WAITED/$MAX_WAIT)"
    sleep 5
    WAITED=$((WAITED + 5))
done

echo "RPyC server is available!"

# Give MT5 a bit more time to fully initialize
sleep 10

# Now start your enhanced connector
echo "Starting Enhanced MT5 Connector..."
python3 /app/mt5_connector_wine_adapter.py &
CONNECTOR_PID=$!

# Function to handle shutdown
cleanup() {
    echo "Shutting down services..."
    [ ! -z "$CONNECTOR_PID" ] && kill $CONNECTOR_PID 2>/dev/null
    [ ! -z "$KASM_PID" ] && kill $KASM_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Monitor processes
echo "============================================"
echo "MT5 Wine Container Status:"
echo "VNC Web Interface: http://localhost:3000"
echo "RPyC Port: 8001"
echo "ZMQ Publisher Port: 5555"
echo "Redis Data Available"
echo "============================================"

# Keep container running and monitor
while true; do
    # Check if connector is still running
    if ! kill -0 $CONNECTOR_PID 2>/dev/null; then
        echo "WARNING: Connector process died! Restarting..."
        python3 /app/mt5_connector_wine_adapter.py &
        CONNECTOR_PID=$!
    fi
    
    # Check if KASM is still running
    if ! kill -0 $KASM_PID 2>/dev/null; then
        echo "ERROR: KASM process died!"
        exit 1
    fi
    
    sleep 30
done