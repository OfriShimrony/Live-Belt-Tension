#!/usr/bin/env python3
"""
Manual Belt Frequency Monitor - Record on Demand
-------------------------------------------------
Press Enter to START a 3-second recording.
Results saved to CSV with belt name and index.

Usage:
    python3 record_on_demand.py <belt_name>
    
Example:
    python3 record_on_demand.py belt_a
    python3 record_on_demand.py belt_b
"""

import requests
import time
import sys
import os
import csv
import numpy as np
from scipy import signal
from datetime import datetime

MOONRAKER_URL = "http://localhost:7125"
MEASUREMENT_DURATION = 3.0

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

def analyze_frequency(filepath, method='y'):
    """
    Quick frequency analysis - returns top 5 frequencies
    
    Default method: 'y' (Y-axis) - works best for CoreXY belt measurements
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
        elif method == 'projection_a':
            signal_data = (accel_x + accel_y) / np.sqrt(2)
        elif method == 'projection_b':
            signal_data = (accel_x - accel_y) / np.sqrt(2)
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
        
        # Find ALL peaks - LOWER THRESHOLD
        noise_floor = np.percentile(belt_mag, 70)  # Was 75, now 70 - more sensitive
        threshold = noise_floor * 1.5  # Was 2.0, now 1.5 - catch weaker peaks
        
        peaks, properties = signal.find_peaks(belt_mag, height=threshold, distance=5)  # Was distance=10
        
        if len(peaks) > 0:
            peak_freqs = belt_freq[peaks]
            peak_mags = belt_mag[peaks]
            
            # Sort by magnitude
            sorted_indices = np.argsort(peak_mags)[::-1]
            
            # Get top 5 (not just 3)
            top_5 = []
            for i in sorted_indices[:5]:
                top_5.append(float(peak_freqs[i]))
            
            return {
                'freq1': top_5[0] if len(top_5) > 0 else 0,
                'freq2': top_5[1] if len(top_5) > 1 else 0,
                'freq3': top_5[2] if len(top_5) > 2 else 0,
                'freq4': top_5[3] if len(top_5) > 3 else 0,
                'freq5': top_5[4] if len(top_5) > 4 else 0,
                'total_peaks': len(peaks),
                'sample_rate': float(sample_rate),
                'samples': len(data)
            }
        
        return None
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return None

def record_measurement(belt_name, index, method='y'):
    """Record a measurement"""
    
    print(f"\n{'='*70}")
    print(f"Recording #{index} for {belt_name}")
    print(f"{'='*70}")
    
    # Start measurement
    print("▶ Starting measurement...")
    send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
    
    print(f"🎸 PLUCK THE BELT NOW!")
    print()
    
    # Countdown with progress bar
    for i in range(int(MEASUREMENT_DURATION)):
        remaining = int(MEASUREMENT_DURATION) - i
        bar = "█" * (i + 1) + "░" * (int(MEASUREMENT_DURATION) - i - 1)
        print(f"\r  Recording: [{bar}] {remaining}s remaining", end='', flush=True)
        time.sleep(1)
    
    print(f"\r  Recording: [{'█' * int(MEASUREMENT_DURATION)}] Complete!   ")
    
    # Stop measurement
    send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME={belt_name}_{index}")
    time.sleep(0.3)
    
    # Analyze
    csv_file = find_latest_csv()
    if csv_file:
        result = analyze_frequency(csv_file, method=method)
        
        if result:
            print()
            print(f"  ✓ Analysis complete")
            print(f"    Samples: {result['samples']} @ {result['sample_rate']:.0f} Hz")
            print(f"    Total peaks found: {result['total_peaks']}")
            print()
            print(f"  Top frequencies:")
            print(f"    1. {result['freq1']:6.1f} Hz")
            if result['freq2'] > 0:
                print(f"    2. {result['freq2']:6.1f} Hz  (2×={result['freq2']*2:.1f} Hz)")
            if result['freq3'] > 0:
                print(f"    3. {result['freq3']:6.1f} Hz  (2×={result['freq3']*2:.1f} Hz)")
            if result['freq4'] > 0:
                print(f"    4. {result['freq4']:6.1f} Hz  (2×={result['freq4']*2:.1f} Hz)")
            if result['freq5'] > 0:
                print(f"    5. {result['freq5']:6.1f} Hz  (2×={result['freq5']*2:.1f} Hz)")
            
            # Check for 2× harmonics in expected range
            print()
            for i, freq_key in enumerate(['freq1', 'freq2', 'freq3', 'freq4', 'freq5'], 1):
                freq = result[freq_key]
                if freq > 0:
                    double = freq * 2
                    if 95 <= double <= 110:
                        print(f"  → Peak #{i} ({freq:.1f} Hz) × 2 = {double:.1f} Hz ✓ IN RANGE!")
            
            return result
        else:
            print("  ✗ No clear peaks detected")
            return None
    else:
        print("  ✗ No data file found")
        return None

def save_to_csv(belt_name, measurements, output_dir='.'):
    """Save all measurements to CSV"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{belt_name}_measurements_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'belt_name',
            'index',
            'timestamp',
            'frequency_1_hz',
            'frequency_2_hz',
            'frequency_3_hz',
            'frequency_4_hz',
            'frequency_5_hz',
            'total_peaks',
            'sample_rate_hz',
            'samples'
        ])
        
        # Data
        for m in measurements:
            writer.writerow([
                m['belt_name'],
                m['index'],
                m['timestamp'],
                m['freq1'],
                m['freq2'],
                m['freq3'],
                m['freq4'],
                m['freq5'],
                m['total_peaks'],
                m['sample_rate'],
                m['samples']
            ])
    
    print(f"\n✓ Results saved to: {filepath}")
    return filepath

def interactive_mode(belt_name, method='y'):
    """Interactive recording mode"""
    
    print("="*70)
    print("BELT FREQUENCY RECORDER")
    print("="*70)
    print(f"Belt: {belt_name.upper()}")
    print(f"Method: {method.upper()}")
    print(f"Recording duration: {MEASUREMENT_DURATION}s")
    print()
    print("Instructions:")
    print("  1. Press ENTER to start recording")
    print("  2. PLUCK the belt when countdown starts")
    print("  3. Wait for analysis")
    print("  4. Repeat or type 'done' to save and exit")
    print("="*70)
    
    measurements = []
    index = 0
    
    while True:
        try:
            user_input = input(f"\n[{index}] Press ENTER to record (or 'done'/'quit'): ").strip().lower()
            
            if user_input in ['done', 'd']:
                if measurements:
                    # Save to CSV
                    output_dir = os.path.dirname(os.path.abspath(__file__))
                    save_to_csv(belt_name, measurements, output_dir)
                    
                    # Summary
                    print()
                    print("="*70)
                    print("SUMMARY")
                    print("="*70)
                    print(f"Total measurements: {len(measurements)}")
                    print()
                    print("Frequency 1 (strongest):")
                    freq1_values = [m['freq1'] for m in measurements]
                    print(f"  Mean: {np.mean(freq1_values):.1f} Hz")
                    print(f"  Std:  {np.std(freq1_values):.1f} Hz")
                    print(f"  Range: {np.min(freq1_values):.1f} - {np.max(freq1_values):.1f} Hz")
                    print("="*70)
                else:
                    print("No measurements recorded.")
                break
            
            elif user_input in ['quit', 'q', 'exit']:
                print("\nExiting without saving...")
                break
            
            # Record measurement
            result = record_measurement(belt_name, index, method)
            
            if result:
                measurements.append({
                    'belt_name': belt_name,
                    'index': index,
                    'timestamp': datetime.now().isoformat(),
                    'freq1': result['freq1'],
                    'freq2': result['freq2'],
                    'freq3': result['freq3'],
                    'freq4': result['freq4'],
                    'freq5': result['freq5'],
                    'total_peaks': result['total_peaks'],
                    'sample_rate': result['sample_rate'],
                    'samples': result['samples']
                })
                index += 1
            
        except KeyboardInterrupt:
            print("\n\nInterrupted!")
            if measurements:
                save_choice = input("Save measurements before exiting? (y/n): ").strip().lower()
                if save_choice == 'y':
                    output_dir = os.path.dirname(os.path.abspath(__file__))
                    save_to_csv(belt_name, measurements, output_dir)
            break
    
    print("\n✓ Done")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 record_on_demand.py <belt_name> [method]")
        print()
        print("Examples:")
        print("  python3 record_on_demand.py belt_a          # Uses Y-axis (recommended)")
        print("  python3 record_on_demand.py belt_b          # Uses Y-axis (recommended)")
        print("  python3 record_on_demand.py belt_a x        # Force X-axis")
        print()
        print("Methods: y (default, recommended), x, magnitude, projection_a, projection_b")
        sys.exit(1)
    
    belt_name = sys.argv[1]
    method = sys.argv[2] if len(sys.argv) > 2 else 'y'
    
    interactive_mode(belt_name, method)

if __name__ == "__main__":
    main()
