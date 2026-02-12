#!/usr/bin/env python3
"""
Simple ADXL345 Data Reader Test Script
--------------------------------------
This script connects to Klipper and requests accelerometer data.
It's a starting point to understand how data flows from the ADXL345.

Usage:
    python3 adxl_test.py

Requirements:
    - Klipper running with ADXL345 configured
    - Run this script on the same machine as Klipper (e.g., Raspberry Pi)
"""

import socket
import json
import time
import sys

# Klipper API socket path (default location)
SOCKET_PATH = "/tmp/klippy_uds"

def connect_to_klipper():
    """Connect to Klipper via Unix socket"""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        print("✓ Connected to Klipper")
        return sock
    except Exception as e:
        print(f"✗ Failed to connect to Klipper: {e}")
        print(f"  Make sure Klipper is running and socket exists at: {SOCKET_PATH}")
        sys.exit(1)

def send_command(sock, command):
    """Send a command to Klipper and get response"""
    try:
        # Format command as JSON
        cmd_dict = {"id": int(time.time() * 1000), "method": command}
        cmd_json = json.dumps(cmd_dict) + "\n"
        
        # Send command
        sock.sendall(cmd_json.encode())
        
        # Receive response (with timeout)
        sock.settimeout(5.0)
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b'\n' in chunk:  # Response complete
                break
        
        # Parse JSON response
        response_str = response.decode().strip()
        if response_str:
            return json.loads(response_str)
        return None
        
    except socket.timeout:
        print("✗ Command timeout - no response from Klipper")
        return None
    except Exception as e:
        print(f"✗ Error sending command: {e}")
        return None

def query_accelerometer(sock):
    """Query current accelerometer values"""
    print("\n--- Querying ADXL345 ---")
    response = send_command(sock, "ACCELEROMETER_QUERY")
    
    if response and "result" in response:
        print(f"Response: {response['result']}")
    else:
        print(f"Raw response: {response}")
    
    return response

def main():
    print("="*50)
    print("ADXL345 Test Script")
    print("="*50)
    
    # Connect to Klipper
    sock = connect_to_klipper()
    
    try:
        # Test 1: Query accelerometer
        print("\nTest 1: Query ADXL345 current values")
        query_accelerometer(sock)
        
        print("\n" + "="*50)
        print("Test complete!")
        print("\nNext steps:")
        print("- If you see accelerometer data above, it's working!")
        print("- We can now build on this to add streaming")
        
    except KeyboardInterrupt:
        print("\n\n✓ Interrupted by user")
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
    finally:
        sock.close()
        print("✓ Connection closed")

if __name__ == "__main__":
    main()
