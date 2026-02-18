#!/usr/bin/env python3
"""
ADXL345 Data Reader via Moonraker API
-------------------------------------
This version uses Moonraker's API which is better suited for
programmatic access to Klipper.

Usage:
    python3 adxl_test_v2.py

Requirements:
    - Klipper running with ADXL345 configured
    - Moonraker running
"""

import requests
import json
import time
import sys

# Moonraker API endpoint (default)
MOONRAKER_URL = "http://localhost:7125"

def test_connection():
    """Test connection to Moonraker"""
    try:
        response = requests.get(f"{MOONRAKER_URL}/server/info", timeout=5)
        if response.status_code == 200:
            print("✓ Connected to Moonraker")
            info = response.json()
            print(f"  Klipper state: {info['result'].get('klippy_state', 'unknown')}")
            return True
        else:
            print(f"✗ Moonraker responded with status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Failed to connect to Moonraker: {e}")
        print(f"  Make sure Moonraker is running at: {MOONRAKER_URL}")
        return False

def send_gcode(gcode_command):
    """Send a G-code command via Moonraker"""
    try:
        url = f"{MOONRAKER_URL}/printer/gcode/script"
        params = {"script": gcode_command}
        response = requests.post(url, params=params, timeout=5)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"✗ Command failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"✗ Error sending command: {e}")
        return None

def get_gcode_store():
    """Get recent G-code console output"""
    try:
        url = f"{MOONRAKER_URL}/server/gcode_store"
        params = {"count": 10}  # Get last 10 messages
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('result', {}).get('gcode_store', [])
        return []
            
    except Exception as e:
        print(f"✗ Error getting console output: {e}")
        return []

def query_accelerometer():
    """Query ADXL345 and capture output"""
    print("\n--- Querying ADXL345 ---")
    
    # Send the query command
    print("Sending ACCELEROMETER_QUERY...")
    result = send_gcode("ACCELEROMETER_QUERY")
    
    if result:
        print("✓ Command sent successfully")
        
        # Wait a moment for Klipper to process
        time.sleep(0.5)
        
        # Get recent console output
        messages = get_gcode_store()
        
        print("\nRecent console output:")
        for msg in messages[-5:]:  # Show last 5 messages
            if 'message' in msg:
                print(f"  {msg['message']}")
                # Look for accelerometer data
                if 'accelerometer values' in msg['message'].lower():
                    print(f"\n✓ Found accelerometer data!")
                    return msg['message']
    
    return None

def main():
    print("="*50)
    print("ADXL345 Test Script (Moonraker API)")
    print("="*50)
    
    # Test connection
    if not test_connection():
        sys.exit(1)
    
    try:
        # Query accelerometer
        print("\nTest: Query ADXL345 current values")
        accel_data = query_accelerometer()
        
        print("\n" + "="*50)
        if accel_data:
            print("✓ Test successful!")
            print(f"\nData: {accel_data}")
        else:
            print("⚠ Test completed but couldn't capture accelerometer output")
            print("  The command worked (check Mainsail console)")
            print("  We may need to use a different method to capture data")
        
        print("\nNext steps:")
        print("- We can now start working on continuous streaming")
        print("- Will need to capture actual accelerometer samples (not just query)")
        
    except KeyboardInterrupt:
        print("\n\n✓ Interrupted by user")
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")

if __name__ == "__main__":
    main()
