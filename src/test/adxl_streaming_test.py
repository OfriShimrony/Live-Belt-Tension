#!/usr/bin/env python3
"""
ADXL345 Continuous Data Collection Test
---------------------------------------
This version uses ACCELEROMETER_MEASURE to collect continuous data,
similar to how Klipper does resonance testing.

Usage:
    python3 adxl_streaming_test.py

Requirements:
    - Klipper running with ADXL345 configured
    - Moonraker running
"""

import requests
import time
import sys
import os

# Moonraker API endpoint (default)
MOONRAKER_URL = "http://localhost:7125"

def test_connection():
    """Test connection to Moonraker"""
    try:
        response = requests.get(f"{MOONRAKER_URL}/server/info", timeout=5)
        if response.status_code == 200:
            print("✓ Connected to Moonraker")
            info = response.json()
            klipper_state = info['result'].get('klippy_state', 'unknown')
            print(f"  Klipper state: {klipper_state}")
            return klipper_state == 'ready'
        return False
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return False

def send_gcode(gcode_command):
    """Send a G-code command via Moonraker"""
    try:
        url = f"{MOONRAKER_URL}/printer/gcode/script"
        params = {"script": gcode_command}
        response = requests.post(url, params=params, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"✗ Error sending command: {e}")
        return False

def get_gcode_store():
    """Get recent G-code console output"""
    try:
        url = f"{MOONRAKER_URL}/server/gcode_store"
        params = {"count": 20}
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('result', {}).get('gcode_store', [])
        return []
    except:
        return []

def find_data_file():
    """Look for the accelerometer data file"""
    # Klipper typically saves to /tmp/
    data_dir = "/tmp"
    
    # Look for recent .csv files
    try:
        files = []
        for filename in os.listdir(data_dir):
            if filename.startswith("adxl345-") and filename.endswith(".csv"):
                filepath = os.path.join(data_dir, filename)
                files.append((filepath, os.path.getmtime(filepath)))
        
        if files:
            # Return most recent file
            files.sort(key=lambda x: x[1], reverse=True)
            return files[0][0]
    except:
        pass
    
    return None

def read_csv_data(filepath, max_lines=20):
    """Read data from CSV file"""
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        # Skip header if present
        data_lines = [l for l in lines if not l.startswith('#')]
        
        return data_lines[:max_lines]
    except Exception as e:
        print(f"✗ Error reading file: {e}")
        return []

def start_measurement(duration=2):
    """Start accelerometer measurement for specified duration"""
    print(f"\n--- Starting {duration}-second measurement ---")
    
    # Start measurement
    cmd = f"ACCELEROMETER_MEASURE CHIP=adxl345"
    print(f"Sending: {cmd}")
    
    if not send_gcode(cmd):
        print("✗ Failed to start measurement")
        return False
    
    print("✓ Measurement started")
    print(f"  Collecting data for {duration} seconds...")
    
    # Wait for measurement duration
    time.sleep(duration)
    
    # Stop measurement
    print("  Stopping measurement...")
    cmd = "ACCELEROMETER_MEASURE CHIP=adxl345 NAME=stop"
    
    if not send_gcode(cmd):
        print("✗ Failed to stop measurement")
        return False
    
    print("✓ Measurement stopped")
    
    # Give Klipper time to write the file
    time.sleep(0.5)
    
    return True

def main():
    print("="*60)
    print("ADXL345 Continuous Streaming Test")
    print("="*60)
    
    # Test connection
    if not test_connection():
        print("✗ Cannot connect to Klipper")
        sys.exit(1)
    
    try:
        # Start measurement
        if not start_measurement(duration=2):
            sys.exit(1)
        
        # Look for the data file
        print("\n--- Looking for data file ---")
        datafile = find_data_file()
        
        if datafile:
            print(f"✓ Found data file: {datafile}")
            
            # Read and display first few lines
            print("\n--- First 20 data points ---")
            data = read_csv_data(datafile, max_lines=20)
            
            if data:
                print(f"Total samples in file: {len(data)} (showing first 20)")
                print("\nFormat: time, accel_x, accel_y, accel_z")
                print("-" * 60)
                for i, line in enumerate(data[:20], 1):
                    print(f"{i:2d}: {line.strip()}")
                
                print("\n" + "="*60)
                print("✓ Successfully collected streaming data!")
                print(f"\nFull data saved to: {datafile}")
                print("\nNext steps:")
                print("- We now have continuous accelerometer data")
                print("- Next: implement FFT analysis on this data")
                print("- Then: make it real-time (live streaming)")
            else:
                print("✗ File is empty or couldn't read it")
        else:
            print("✗ Couldn't find data file")
            print("  Check console output for file location:")
            messages = get_gcode_store()
            for msg in messages[-10:]:
                if 'message' in msg:
                    print(f"    {msg['message']}")
        
    except KeyboardInterrupt:
        print("\n\n✓ Interrupted by user")
        print("  Stopping measurement...")
        send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345 NAME=stop")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
