#!/usr/bin/env python3
"""
Simple Belt Frequency Monitor
------------------------------
Continuously shows belt frequency readings in terminal.
Simple, fast, frequent updates.

Usage:
    python3 simple_monitor.py [axis] [method]
    
    axis: x, y, or magnitude (default: magnitude)
    method: Use 'magnitude' for vector magnitude, or 'x'/'y' for individual axis
"""

import requests
import time
import sys
import os
import numpy as np
from scipy import signal

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

def analyze_frequency(filepath, method='magnitude'):
    """
    Quick frequency analysis
    
    Args:
        filepath: Path to CSV file
        method: 'x', 'y', or 'magnitude'
    """
    try:
        data = np.genfromtxt(filepath, delimiter=',', skip_header=1)
        if len(data) < 500:
            return None
        
        times = data[:, 0]
        accel_x = data[:, 1]
        accel_y = data[:, 2]
        
        # Calculate sample rate
        dt = np.mean(np.diff(times))
        sample_rate = 1.0 / dt
        
        # Select signal based on method
        if method == 'x':
            signal_data = accel_x
        elif method == 'y':
            signal_data = accel_y
        else:  # magnitude
            signal_data = np.sqrt(accel_x**2 + accel_y**2)
        
        # Remove DC
        signal_data = signal_data - np.mean(signal_data)
        
        # Window and FFT
        window = np.hanning(len(signal_data))
        windowed = signal_data * window
        
        fft_result = np.fft.rfft(windowed)
        fft_freq = np.fft.rfftfreq(len(windowed), 1.0/sample_rate)
        fft_mag = np.abs(fft_result)
        
        # Belt frequency range
        belt_range = (fft_freq >= 50) & (fft_freq <= 200)
        belt_freq = fft_freq[belt_range]
        belt_mag = fft_mag[belt_range]
        
        if len(belt_mag) == 0:
            return None
        
        # Find strongest peak
        noise_floor = np.percentile(belt_mag, 75)
        threshold = noise_floor * 2
        
        peaks, _ = signal.find_peaks(belt_mag, height=threshold, distance=10)
        
        if len(peaks) > 0:
            peak_freqs = belt_freq[peaks]
            peak_mags = belt_mag[peaks]
            
            # Get strongest
            strongest_idx = np.argmax(peak_mags)
            freq = peak_freqs[strongest_idx]
            mag = peak_mags[strongest_idx]
            
            return {
                'frequency': float(freq),
                'magnitude': float(mag),
                'sample_rate': float(sample_rate),
                'samples': len(data)
            }
        
        return None
        
    except Exception as e:
        return None

def continuous_monitor(method='magnitude', interval=1.5):
    """
    Continuously monitor belt frequency
    
    Args:
        method: 'x', 'y', or 'magnitude'
        interval: Seconds between measurements
    """
    
    print("="*70)
    print("SIMPLE BELT FREQUENCY MONITOR")
    print("="*70)
    print(f"Method: {method.upper()}")
    print(f"Measurement interval: {interval}s")
    print(f"Target range: 100-140 Hz (typical)")
    print()
    print("Instructions:")
    print("  1. Start: The monitor will begin measuring automatically")
    print("  2. Pluck belt when ready")
    print("  3. Watch frequency update")
    print("  4. Ctrl+C to stop")
    print("="*70)
    print()
    
    # Start continuous measurement
    print("Starting measurement...")
    send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
    time.sleep(0.5)
    
    measurement_count = 0
    last_file = None
    
    try:
        while True:
            # Stop and restart to get fresh data
            send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=monitor_{measurement_count}")
            time.sleep(0.3)
            
            # Analyze latest file
            csv_file = find_latest_csv()
            if csv_file and csv_file != last_file:
                result = analyze_frequency(csv_file, method=method)
                
                if result:
                    freq = result['frequency']
                    
                    # Simple status indicator
                    if 100 <= freq <= 140:
                        status = "✓ GOOD"
                        bar = "█" * 20
                    elif freq < 100:
                        status = "⬇ LOW"
                        bar = "░" * 10 + "█" * 10
                    else:
                        status = "⬆ HIGH"
                        bar = "█" * 10 + "░" * 10
                    
                    # Print update
                    print(f"\r{freq:6.1f} Hz  [{bar}]  {status}   ", end='', flush=True)
                    
                    last_file = csv_file
                else:
                    print(f"\r  --.- Hz  [{'?' * 20}]  WAITING  ", end='', flush=True)
            
            # Start next measurement
            send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
            measurement_count += 1
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\n\nStopping...")
        send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345 NAME=stop")
        print("✓ Stopped")
        print()

def main():
    # Parse arguments
    method = 'magnitude'  # default
    interval = 1.5  # default
    
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ['x', 'y', 'magnitude', 'mag']:
            method = 'magnitude' if arg == 'mag' else arg
    
    if len(sys.argv) > 2:
        try:
            interval = float(sys.argv[2])
        except:
            pass
    
    continuous_monitor(method=method, interval=interval)

if __name__ == "__main__":
    main()
