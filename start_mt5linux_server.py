#!/usr/bin/env python3
# start_mt5linux_server.py - Correct way to start mt5linux server

import os
import sys
import subprocess
import time
import logging

# Set up environment
os.environ['DISPLAY'] = ':99'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_server():
    """Start mt5linux server using subprocess"""
    try:
        # The correct way to start mt5linux server is using the module as a script
        # with specific parameters
        cmd = [
            sys.executable,
            '-m', 'mt5linux',
            '--host', '0.0.0.0',
            '--port', '18812'
        ]
        
        logger.info(f"Starting mt5linux server with command: {' '.join(cmd)}")
        
        # Start the server process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Give it time to start
        time.sleep(5)
        
        # Check if process is still running
        if process.poll() is None:
            logger.info(f"mt5linux server started successfully with PID: {process.pid}")
            
            # Monitor the output
            while True:
                output = process.stdout.readline()
                if output:
                    logger.info(f"mt5linux: {output.strip()}")
                
                # Check if process is still alive
                if process.poll() is not None:
                    logger.error("mt5linux server process terminated")
                    break
                    
        else:
            # Process terminated, get output
            stdout, _ = process.communicate()
            logger.error(f"mt5linux server failed to start. Output:\n{stdout}")
            return 1
            
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(start_server())