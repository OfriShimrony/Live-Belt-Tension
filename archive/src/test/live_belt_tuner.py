#!/usr/bin/env python3
"""
Live Belt Tension Tuner
-----------------------
Continuously moves the toolhead and shows frequency readings in real-time.
Press Q to stop.

Belt A: X175,Y98 → X225,Y48 → X125,Y148 → X225,Y48 (loop)
Belt B: X175,Y98 → X125,Y48 → X225,Y148 → X125,Y48 (loop)

Usage:
    python3 live_belt_tuner.py <belt>
    
Examples:
    python3 live_belt_tuner.py a
    python3 live_belt_tuner.py b
"""

import requests
import time
import sys
import os
import threading
import numpy as np
from scipy import signal

MOONRAKER_URL = "http://localhost:7125"
MEASUREMENT_ACTIVE = False
STOP_REQUESTED = False

def send_gcode(command):
    """Send G-code command"""
    try:
        url = f"{MOONRAKER_URL}/printer/gcode/script"
        params = {"script": command}
        response = requests.post(url, params=params, timeout=10)
        return response.status_code == 200
    except:
        return False

def find_latest_csv():
    """Find most recent CSV file"""
    data_dir = "/tmp"
    try:
        files = []
        for filename in os.listdir(data_dir):
            if filename.startswith("adxl345-") and filename.endswith(".csv"):
                filepath = os.path.join(data_dir, filename)
                files.append((filepath, os.path.getmtime(filepath)))
        
        if files:
            files.sort(key=lambda x: x[1], reverse=True)
            return files[0][0]
    except:
        pass
    return None

def analyze_frequency_quick(filepath):
    """Quick Y-axis frequency analysis - returns best frequency in 95-115 Hz range"""
    try:
        data = np.genfromtxt(filepath, delimiter=',', skip_header=1)
        if len(data) < 300:  # Need at least some samples
            return None
        
        times = data[:, 0]
        accel_y = data[:, 2]  # Y-axis
        
        dt = np.mean(np.diff(times))
        sample_rate = 1.0 / dt
        
        # FFT
        signal_data = accel_y - np.mean(accel_y)
        window = np.hanning(len(signal_data))
        windowed = signal_data * window
        
        fft_result = np.fft.rfft(windowed)
        fft_freq = np.fft.rfftfreq(len(windowed), 1.0/sample_rate)
        fft_mag = np.abs(fft_result)
        
        # Belt range
        belt_range = (fft_freq >= 50) & (fft_freq <= 200)
        belt_freq = fft_freq[belt_range]
        belt_mag = fft_mag[belt_range]
        
        if len(belt_mag) == 0:
            return None
        
        # Find peaks
        noise_floor = np.percentile(belt_mag, 70)
        threshold = noise_floor * 1.5
        peaks, _ = signal.find_peaks(belt_mag, height=threshold, distance=5)
        
        if len(peaks) > 0:
            peak_freqs = belt_freq[peaks]
            peak_mags = belt_mag[peaks]
            
            # Sort by magnitude and return strongest peak
            sorted_indices = np.argsort(peak_mags)[::-1]
            return float(peak_freqs[sorted_indices[0]])
        
        return None
        
    except Exception as e:
        return None

def input_listener():
    """Listen for Q key press in separate thread"""
    global STOP_REQUESTED
    while not STOP_REQUESTED:
        user_input = input()
        if user_input.strip().lower() == 'q':
            STOP_REQUESTED = True
            print("\n⚠ Stop requested - will finish current cycle...")
            break

def live_tuning(belt):
    """Run live belt tuning with continuous movement and frequency readings"""
    global MEASUREMENT_ACTIVE, STOP_REQUESTED
    
    belt_name = f"Belt {belt.upper()}"
    
    print("="*70)
    print("LIVE BELT TENSION TUNER")
    print("="*70)
    print(f"Belt: {belt_name}")
    print()
    
    if belt.lower() == 'a':
        print("Movement pattern (Belt A):")
        print("  Start:    X175 Y98  (15cm reference point)")
        print("  Move to:  X225 Y48  (start position)")
        print("  Loop:     X225,Y48 → X125,Y148 → X225,Y48")
        print("  Manual return to X175 Y98 when done")
    else:
        print("Movement pattern (Belt B):")
        print("  Start:    X175 Y98  (15cm reference point)")
        print("  Move to:  X125 Y48  (start position)")
        print("  Loop:     X125,Y48 → X225,Y148 → X125,Y48")
        print("  Manual return to X175 Y98 when done")
    
    print()
    print("Instructions:")
    print("  - Position toolhead at X175 Y98")
    print("  - Script will move to start position and begin loop")
    print("  - Frequency shown after each pass")
    print("  - Press Q and ENTER to stop")
    print("="*70)
    print()
    
    input("Press ENTER to start...")
    
    # Start input listener thread
    listener_thread = threading.Thread(target=input_listener, daemon=True)
    listener_thread.start()
    
    print("\nPress Q and ENTER to stop\n")
    
    # Start continuous measurement
    print("Starting accelerometer measurement...")
    send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
    MEASUREMENT_ACTIVE = True
    time.sleep(0.5)
    
    # Move to start position
    print("Moving to start position...")
    send_gcode("G90")  # Absolute positioning
    
    if belt.lower() == 'a':
        # Belt A: Move to X225 Y48 (then X-Y diagonal movement)
        send_gcode("G0 X225 Y48 F12000")
        time.sleep(1)
        start_x, start_y = 225, 48
        end_x, end_y = 125, 148
    else:
        # Belt B: Move to X125 Y48 (then X+Y diagonal movement)
        send_gcode("G0 X125 Y48 F12000")
        time.sleep(1)
        start_x, start_y = 125, 48
        end_x, end_y = 225, 148
    
    print(f"At start position: X{start_x} Y{start_y}")
    print()
    print("="*70)
    print("Cycle  Direction         Frequency (Hz)    Status")
    print("-"*70)
    
    cycle = 1
    last_file = None
    last_file_time = 0
    
    try:
        while not STOP_REQUESTED:
            # Move to end position
            send_gcode(f"G0 X{end_x} Y{end_y} F12000")
            time.sleep(1.2)  # Increased wait time for movement + data collection
            
            # Stop and restart measurement to get fresh file
            send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=cycle_{cycle}_fwd")
            time.sleep(0.3)
            send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
            time.sleep(0.2)
            
            # Analyze
            csv_file = find_latest_csv()
            if csv_file:
                file_time = os.path.getmtime(csv_file)
                if file_time > last_file_time:
                    freq = analyze_frequency_quick(csv_file)
                    if freq:
                        # Expanded status range
                        if 100 <= freq <= 115:
                            status = "✓ TARGET"
                        elif 90 <= freq <= 125:
                            status = "⚠ OK"
                        elif freq > 125:
                            status = f"⬆ HIGH"
                        else:
                            status = f"⬇ LOW"
                        print(f" {cycle:3d}   Forward  X{start_x},Y{start_y}→X{end_x},Y{end_y}   {freq:6.1f} Hz   {status}")
                    else:
                        print(f" {cycle:3d}   Forward  X{start_x},Y{start_y}→X{end_x},Y{end_y}      --.- Hz      ? (no peaks)")
                    last_file_time = file_time
                else:
                    print(f" {cycle:3d}   Forward  X{start_x},Y{start_y}→X{end_x},Y{end_y}      --.- Hz      ? (old file)")
            else:
                print(f" {cycle:3d}   Forward  X{start_x},Y{start_y}→X{end_x},Y{end_y}      --.- Hz      ? (no file)")
            
            if STOP_REQUESTED:
                break
            
            # Move back to start
            send_gcode(f"G0 X{start_x} Y{start_y} F12000")
            time.sleep(1.2)
            
            # Stop and restart measurement
            send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=cycle_{cycle}_ret")
            time.sleep(0.3)
            send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
            time.sleep(0.2)
            
            # Analyze
            csv_file = find_latest_csv()
            if csv_file:
                file_time = os.path.getmtime(csv_file)
                if file_time > last_file_time:
                    freq = analyze_frequency_quick(csv_file)
                    if freq:
                        # Expanded status range
                        if 100 <= freq <= 115:
                            status = "✓ TARGET"
                        elif 90 <= freq <= 125:
                            status = "⚠ OK"
                        elif freq > 125:
                            status = f"⬆ HIGH"
                        else:
                            status = f"⬇ LOW"
                        print(f" {cycle:3d}   Return   X{end_x},Y{end_y}→X{start_x},Y{start_y}   {freq:6.1f} Hz   {status}")
                    else:
                        print(f" {cycle:3d}   Return   X{end_x},Y{end_y}→X{start_x},Y{start_y}      --.- Hz      ? (no peaks)")
                    last_file_time = file_time
                else:
                    print(f" {cycle:3d}   Return   X{end_x},Y{end_y}→X{start_x},Y{start_y}      --.- Hz      ? (old file)")
            else:
                print(f" {cycle:3d}   Return   X{end_x},Y{end_y}→X{start_x},Y{start_y}      --.- Hz      ? (no file)")
            
            cycle += 1
            
            if STOP_REQUESTED:
                break
    
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted!")
    
    finally:
        # Stop measurement
        if MEASUREMENT_ACTIVE:
            print("\n" + "="*70)
            print("Stopping measurement...")
            send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=live_{belt}")
            MEASUREMENT_ACTIVE = False
        
        print()
        print("✓ Tuning session complete")
        print(f"  Total cycles: {cycle - 1}")
        print()
        print("NEXT STEP:")
        print(f"  Manually return toolhead to X175 Y98")
        print()

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 live_belt_tuner.py <belt>")
        print()
        print("Examples:")
        print("  python3 live_belt_tuner.py a")
        print("  python3 live_belt_tuner.py b")
        sys.exit(1)
    
    belt = sys.argv[1].lower()
    
    if belt not in ['a', 'b']:
        print("Belt must be 'a' or 'b'")
        sys.exit(1)
    
    live_tuning(belt)

if __name__ == "__main__":
    main()
