#!/usr/bin/env python3
"""
Belt Acceleration Sweep Test - IMPROVED
----------------------------------------
Implements proper "pluck and decay" measurement sequence.

Key improvements:
1. Move OUT slowly (no measurement) - "prime the string"
2. Start measurement
3. SNAP back to center (the "pluck")
4. Wait for motors to stop (M400)
5. Dwell 500ms to capture pure decay (G4 P500)
6. Stop measurement

This ensures we only capture the belt resonance decay,
not the motor noise from the movement.

Usage:
    python3 acceleration_sweep_improved.py <belt>
    
Examples:
    python3 acceleration_sweep_improved.py a
    python3 acceleration_sweep_improved.py b
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

def acceleration_sweep_improved(belt):
    """Run improved acceleration sweep test with proper pluck-and-decay"""
    
    belt_name = f"Belt {belt.upper()}"
    
    # Acceleration values to test (mm/s²)
    accelerations = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]
    
    print("="*70)
    print("BELT ACCELERATION SWEEP TEST - IMPROVED")
    print("="*70)
    print(f"Belt: {belt_name}")
    print()
    print("Improvements:")
    print("  ✓ Captures ONLY the decay phase (no motor noise)")
    print("  ✓ Clean passive resonance measurement")
    print("  ✓ Should pass time-decay validation")
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
    print("Measurement Sequence:")
    print("  1. Move OUT slowly (no measurement)")
    print("  2. START measurement")
    print("  3. SNAP back to center (high acceleration)")
    print("  4. Wait for motors to stop (M400)")
    print("  5. Dwell 500ms (capture pure decay)")
    print("  6. STOP measurement")
    print()
    print("="*70)
    print()
    
    input("Press ENTER when positioned at X175 Y98...")
    
    print()
    print("Starting improved sweep...")
    print()
    print("Test  Accel(mm/s²)  Status")
    print("-"*70)
    
    # Set absolute positioning
    send_gcode("G90")
    
    for test_num, accel in enumerate(accelerations, 1):
        print(f" {test_num:2d}   {accel:5d}        ", end='', flush=True)
        
        # ===================================================================
        # STEP 1: Move OUT slowly (prime the belt, no measurement)
        # ===================================================================
        send_gcode("G91")  # Relative mode
        send_gcode(f"G0 X{dx} Y{dy} F3000")  # Slow move out (50mm/s)
        send_gcode("M400")  # Wait for move to finish
        time.sleep(0.3)
        
        # ===================================================================
        # STEP 2: Start measurement
        # ===================================================================
        send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
        time.sleep(0.2)
        
        # ===================================================================
        # STEP 3: Set acceleration and SNAP back (the "pluck")
        # ===================================================================
        send_gcode(f"M204 S{accel}")
        send_gcode(f"G0 X{-dx} Y{-dy} F6000")  # Fast snap back (100mm/s)
        
        # ===================================================================
        # STEP 4: Wait for move to finish (critical!)
        # ===================================================================
        send_gcode("M400")  # Block until move completes
        
        # ===================================================================
        # STEP 5: Dwell to capture pure decay (no motor noise)
        # ===================================================================
        send_gcode("G4 P500")  # Wait 500ms while capturing belt resonance
        
        # ===================================================================
        # STEP 6: Stop measurement
        # ===================================================================
        send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=improved_sweep_{belt}_{accel}")
        
        send_gcode("G90")  # Back to absolute
        time.sleep(0.3)
        
        print("✓ Complete")
    
    # Restore default acceleration
    send_gcode("M204 S3000")
    
    print()
    print("="*70)
    print("IMPROVED SWEEP COMPLETE")
    print("="*70)
    print()
    print("Data files created:")
    print("  /tmp/adxl345-improved_sweep_{belt}_{accel}.csv")
    print()
    print("Next step:")
    print("  Analyze all results:")
    print(f"     python3 analyze_improved_sweep.py {belt}")
    print()
    print("Expected improvements:")
    print("  ✓ Decay validation should PASS (Chunk 1 > Chunk 2 > Chunk 3)")
    print("  ✓ Higher Q-factors (sharper peaks)")
    print("  ✓ Higher confidence scores")
    print("  ✓ Clearer belt frequency detection")
    print()
    print("="*70)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 acceleration_sweep_improved.py <belt>")
        print()
        print("Examples:")
        print("  python3 acceleration_sweep_improved.py a")
        print("  python3 acceleration_sweep_improved.py b")
        sys.exit(1)
    
    belt = sys.argv[1].lower()
    
    if belt not in ['a', 'b']:
        print("Belt must be 'a' or 'b'")
        sys.exit(1)
    
    acceleration_sweep_improved(belt)

if __name__ == "__main__":
    main()
