#!/usr/bin/env python3
"""
Simple Belt Frequency Test
---------------------------
Quick test of manual pluck detection.

Usage:
    1. Position toolhead
    2. Run: python3 belt_test_simple.py A
    3. When prompted, manually pluck the belt
    4. Script measures for 2 seconds
    5. Results display

This uses all our improved signal processing.
"""

import requests
import time
import sys
import os
from belt_pluck_detector import analyze_pluck, send_gcode, find_latest_csv

def simple_test(belt_name):
    """Run a simple single-measurement test"""
    
    print("\n" + "="*70)
    print(f"BELT {belt_name} - MANUAL PLUCK TEST")
    print("="*70)
    print()
    print("Instructions:")
    print("  1. Position the toolhead (e.g., X175 Y98)")
    print("  2. Press ENTER to start measurement")
    print("  3. PLUCK THE BELT when countdown starts")
    print("  4. Wait for analysis")
    print()
    
    input("Press ENTER when ready to start...")
    
    print()
    print("Starting measurement...")
    
    # Start ADXL measurement
    send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
    time.sleep(0.3)
    
    # Countdown
    print("Pluck the belt in:")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(0.8)
    
    print("  PLUCK NOW!")
    print()
    
    # Let the belt ring for 2 seconds
    time.sleep(2.0)
    
    # Stop measurement
    print("Stopping measurement...")
    send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=belt_{belt_name}_test")
    time.sleep(0.5)
    
    # Find and analyze the file
    print("Analyzing...")
    csv_file = find_latest_csv()
    
    if not csv_file:
        print("✗ No data file found")
        return
    
    result = analyze_pluck(csv_file, belt_name)
    
    if 'error' in result:
        print(f"✗ Error: {result['error']}")
        return
    
    # Display results
    print()
    print("="*70)
    print("RESULTS")
    print("="*70)
    print(f"Frequency: {result['frequency']:.1f} Hz")
    print(f"Confidence: {result['confidence']}")
    print(f"Q-Factor: {result['q_factor']:.1f} (peak sharpness)")
    print(f"SNR: {result['snr']:.1f}:1")
    print(f"Decay: {'✓ YES' if result.get('is_decaying') else '✗ NO'}")
    print(f"Score: {result['score']}/10")
    print()
    
    # Show all detected peaks
    if 'all_candidates' in result and len(result['all_candidates']) > 1:
        print("Other detected frequencies:")
        for i, cand in enumerate(result['all_candidates'][1:4], 2):
            print(f"  {i}. {cand['freq']:6.1f} Hz (Q={cand['q_factor']:.1f}, SNR={cand['snr']:.1f}x)")
        print()
    
    # Interpretation
    if result['confidence'] == 'HIGH':
        print("✓ HIGH confidence - This is likely the correct belt frequency")
    elif result['confidence'] == 'MEDIUM':
        print("⚠ MEDIUM confidence - Result is plausible but verify with manual tuner")
    else:
        print("✗ LOW confidence - Signal quality poor, try again with harder pluck")
    
    print("="*70)
    print()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 belt_test_simple.py <belt>")
        print()
        print("Examples:")
        print("  python3 belt_test_simple.py A")
        print("  python3 belt_test_simple.py B")
        sys.exit(1)
    
    belt = sys.argv[1].upper()
    
    if belt not in ['A', 'B']:
        print("Belt must be 'A' or 'B'")
        sys.exit(1)
    
    simple_test(belt)

if __name__ == "__main__":
    main()
