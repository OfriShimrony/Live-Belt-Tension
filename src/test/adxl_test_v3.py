#!/usr/bin/env python3
"""
ADXL345 Data Reader with Parsed Values
--------------------------------------
This version parses the accelerometer data into usable numbers.

Usage:
    python3 adxl_test_v3.py

Requirements:
    - Klipper running with ADXL345 configured
    - Moonraker running
"""

import requests
import json
import time
import sys
import re

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
            return None
            
    except Exception as e:
        print(f"✗ Error sending command: {e}")
        return None

def get_gcode_store():
    """Get recent G-code console output"""
    try:
        url = f"{MOONRAKER_URL}/server/gcode_store"
        params = {"count": 10}
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('result', {}).get('gcode_store', [])
        return []
            
    except Exception as e:
        print(f"✗ Error getting console output: {e}")
        return []

def parse_accelerometer_data(message):
    """
    Parse accelerometer output into X, Y, Z values
    
    Input format: "// accelerometer values (x, y, z): 74.020594, 74.020594, 10265.679673"
    Returns: dict with 'x', 'y', 'z' as floats, or None if parsing fails
    """
    # Look for pattern: (x, y, z): float, float, float
    pattern = r'accelerometer values.*:\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)'
    match = re.search(pattern, message)
    
    if match:
        try:
            return {
                'x': float(match.group(1)),
                'y': float(match.group(2)),
                'z': float(match.group(3))
            }
        except ValueError:
            return None
    return None

def query_accelerometer():
    """Query ADXL345 and return parsed values"""
    # Send the query command
    result = send_gcode("ACCELEROMETER_QUERY")
    
    if not result:
        return None
    
    # Wait for Klipper to process
    time.sleep(0.3)
    
    # Get recent console output
    messages = get_gcode_store()
    
    # Look for accelerometer data in recent messages
    for msg in reversed(messages):  # Check most recent first
        if 'message' in msg:
            data = parse_accelerometer_data(msg['message'])
            if data:
                return data
    
    return None

def main():
    print("="*60)
    print("ADXL345 Test Script - Parsed Data Version")
    print("="*60)
    
    # Test connection
    if not test_connection():
        sys.exit(1)
    
    try:
        print("\n--- Querying ADXL345 ---\n")
        
        # Take 5 samples to show data variation
        print("Taking 5 samples (1 per second)...\n")
        
        for i in range(5):
            data = query_accelerometer()
            
            if data:
                # Display nicely formatted data
                print(f"Sample {i+1}:")
                print(f"  X: {data['x']:>10.2f} mm/s²")
                print(f"  Y: {data['y']:>10.2f} mm/s²")
                print(f"  Z: {data['z']:>10.2f} mm/s²")
                
                # Calculate magnitude (total acceleration)
                magnitude = (data['x']**2 + data['y']**2 + data['z']**2) ** 0.5
                print(f"  Magnitude: {magnitude:>6.2f} mm/s²")
                print()
            else:
                print(f"Sample {i+1}: Failed to get data")
                print()
            
            # Wait before next sample (except on last iteration)
            if i < 4:
                time.sleep(1)
        
        print("="*60)
        print("✓ Test complete!")
        print("\nObservations:")
        print("- X and Y should be near zero when printer is still")
        print("- Z should be ~9800 mm/s² (gravity)")
        print("- Your Z value seems high - might be sensor orientation")
        print("\nNext steps:")
        print("- Ready to implement continuous streaming")
        print("- Will need FFT analysis to extract belt frequencies")
        
    except KeyboardInterrupt:
        print("\n\n✓ Interrupted by user")
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
