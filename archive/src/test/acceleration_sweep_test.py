#!/usr/bin/env python3
"""
Belt Acceleration Sweep Test
-----------------------------
Tests different accelerations to find optimal excitation.

From X175 Y98 (center, 15cm point):
- Diagonal movement 20mm (Belt A: X+20 Y-20 or Belt B: X+20 Y+20)
- Return to center
- Repeat with increasing acceleration: 1000, 2000, ..., 9000 mm/s²

Each measurement is analyzed to see which acceleration gives:
- Highest Q-factor (sharpest peak)
- Best decay profile (proves resonance)
- Cleanest signal

Usage:
    python3 acceleration_sweep_test.py <belt>
    
Examples:
    python3 acceleration_sweep_test.py a
    python3 acceleration_sweep_test.py b
"""

import requests
import time
import sys
import os

MOONRAKER_URL = "http://localhost:7125"

def send_gcode(command):
    """Send G-code command"""
    try:
        url = f"{MOONRAKER_URL}/printer/gcode/script"
        params = {"script": command}
        response = requests.post(url, params=params, timeout=10)
        return response.status_code == 200
    except:
        return False

def acceleration_sweep_test(belt):
    """Run acceleration sweep test"""
    
    belt_name = f"Belt {belt.upper()}"
    
    # Acceleration values to test (mm/s²)
    accelerations = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]
    
    print("="*70)
    print("BELT ACCELERATION SWEEP TEST")
    print("="*70)
    print(f"Belt: {belt_name}")
    print()
    print("Test Parameters:")
    print("  Starting position: X175 Y98 (15cm reference point)")
    print("  Movement: 20mm diagonal")
    print(f"  Accelerations: {accelerations[0]} to {accelerations[-1]} mm/s² (9 steps)")
    print()
    
    if belt.lower() == 'a':
        print("  Belt A diagonal: X+20 Y-20 (opposite directions)")
        dx, dy = 20, -20
    else:
        print("  Belt B diagonal: X+20 Y+20 (same direction)")
        dx, dy = 20, 20
    
    print()
    print("Instructions:")
    print("  - Position toolhead at X175 Y98")
    print("  - Script will test each acceleration automatically")
    print("  - ~90 seconds total test time")
    print("="*70)
    print()
    
    input("Press ENTER when positioned at X175 Y98...")
    
    print()
    print("Starting sweep...")
    print()
    print("Test  Accel(mm/s²)  Status")
    print("-"*70)
    
    # Save current acceleration
    send_gcode("M204 S3000")  # Default
    
    # Set absolute positioning
    send_gcode("G90")
    
    for test_num, accel in enumerate(accelerations, 1):
        print(f" {test_num:2d}   {accel:5d}        ", end='', flush=True)
        
        # Set acceleration
        send_gcode(f"M204 S{accel}")
        time.sleep(0.1)
        
        # Start measurement
        send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
        time.sleep(0.3)
        
        # Execute diagonal movement (impulse)
        send_gcode("G91")  # Relative mode
        send_gcode(f"G0 X{dx} Y{dy} F6000")  # Move out (100mm/s)
        time.sleep(0.3)
        
        # Pause to let vibrations develop
        time.sleep(0.5)
        
        # Return to center
        send_gcode(f"G0 X{-dx} Y{-dy} F6000")  # Move back
        time.sleep(0.3)
        
        send_gcode("G90")  # Back to absolute
        
        # Wait for vibrations to settle
        time.sleep(1.0)
        
        # Stop measurement
        send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=accel_sweep_{belt}_{accel}")
        time.sleep(0.3)
        
        print("✓ Complete")
    
    # Restore default acceleration
    send_gcode("M204 S3000")
    
    print()
    print("="*70)
    print("SWEEP COMPLETE")
    print("="*70)
    print()
    print("Data files created:")
    print("  /tmp/adxl345-accel_sweep_{belt}_{accel}.csv")
    print()
    print("Next steps:")
    print("  1. Analyze each file with the complete pipeline:")
    print(f"     python3 belt_analysis_complete.py /tmp/adxl345-accel_sweep_{belt}_1000.csv")
    print(f"     python3 belt_analysis_complete.py /tmp/adxl345-accel_sweep_{belt}_2000.csv")
    print("     ... etc")
    print()
    print("  2. Compare Q-factors and confidence scores")
    print("  3. Find the acceleration that gives the cleanest signal")
    print()
    print("="*70)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 acceleration_sweep_test.py <belt>")
        print()
        print("Examples:")
        print("  python3 acceleration_sweep_test.py a")
        print("  python3 acceleration_sweep_test.py b")
        sys.exit(1)
    
    belt = sys.argv[1].lower()
    
    if belt not in ['a', 'b']:
        print("Belt must be 'a' or 'b'")
        sys.exit(1)
    
    acceleration_sweep_test(belt)

if __name__ == "__main__":
    main()
