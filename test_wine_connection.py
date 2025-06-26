import redis
import json
import time

print("Testing MT5 Wine connection with new ports...")
r = redis.Redis(host='localhost', port=6382, decode_responses=True)

# Wait a bit for MT5 to initialize
print("Waiting for MT5 to initialize (this can take 2-3 minutes on first run)...")
time.sleep(30)

# Check MT5 status
status = r.hgetall('mt5:status')
if status:
    print("\n✓ MT5 Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")
else:
    print("\n⚠ MT5 not connected yet. This is normal on first run.")
    print("  The Wine environment needs time to initialize.")
    print("  Check VNC at http://your-server-ip:3001")

# Check for any data
account = r.hgetall('mt5:account')
if account:
    print("\n✓ Account Info:")
    for key, value in account.items():
        print(f"  {key}: {value}")
