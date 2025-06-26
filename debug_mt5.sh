# Debug and Fix MT5 Connection

# 1. Check what's actually running inside the container
echo "=== Checking MT5 Container Internals ==="
docker exec mt5-real ps aux | grep -E "(python|rpyc|wine|meta)" || echo "No relevant processes"

# 2. Check what's listening on port 8001
echo -e "\n=== Port 8001 Status ==="
docker exec mt5-real netstat -tlnp | grep 8001 || echo "Port 8001 not listening"

# 3. Check if there are any RPyC servers running
echo -e "\n=== RPyC Process Check ==="
docker exec mt5-real pgrep -f rpyc || echo "No RPyC processes"

# 4. Look for Python files in the container
echo -e "\n=== Python Files in Container ==="
docker exec mt5-real find / -name "*.py" -path "*/app/*" 2>/dev/null | head -10

# 5. Check container startup scripts
echo -e "\n=== Container Startup Scripts ==="
docker exec mt5-real ls -la /etc/services.d/ 2>/dev/null || echo "No services.d"
docker exec mt5-real ls -la /etc/cont-init.d/ 2>/dev/null || echo "No cont-init.d"

# 6. Try to manually start the RPyC server inside container
echo -e "\n=== Attempting to Start RPyC Server Manually ==="
docker exec mt5-real bash -c "
echo 'Checking if MetaTrader5 Python module is available...'
python3 -c 'import MetaTrader5; print(\"MT5 module available\")' 2>/dev/null || echo 'MT5 module not found'

echo 'Trying to start RPyC classic server...'
python3 -c '
import rpyc
from rpyc.utils.classic import DEFAULT_SERVER_PORT
from rpyc.utils.server import ThreadedServer
from rpyc.core.service import ClassicService

try:
    print(\"Starting RPyC classic server on port 8001...\")
    server = ThreadedServer(ClassicService, port=8001, auto_register=False)
    print(\"Server created, starting...\")
    # Don not actually start it, just test creation
    print(\"RPyC classic server can be created\")
except Exception as e:
    print(f\"Failed to create RPyC server: {e}\")
' &
"

# 7. Check container logs for any Python/RPyC startup messages
echo -e "\n=== Full Container Logs Search ==="
docker logs mt5-real 2>&1 | grep -i -E "(python|rpyc|8001|server|mt5)" | tail -20 || echo "No relevant log entries"

# 8. Try different approach - check if we can access MT5 directly
echo -e "\n=== Direct MT5 Access Test ==="
docker exec mt5-real bash -c "
export DISPLAY=:1
cd /config/.wine/drive_c/Program\ Files/MetaTrader\ 5/ 2>/dev/null || cd /root/.wine/drive_c/Program\ Files/MetaTrader\ 5/ 2>/dev/null || echo 'MT5 path not found'
ls -la terminal64.exe 2>/dev/null || echo 'MT5 executable not found'
"