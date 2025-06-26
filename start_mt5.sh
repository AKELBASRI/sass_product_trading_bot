### start_mt5.sh

#!/bin/bash

# Start Xvfb (virtual display)
Xvfb :99 -screen 0 1024x768x16 &

# Wait for display to be ready
sleep 2

# Start MT5 connector
python3 /mt5/mt5_connector.py
