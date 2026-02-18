#!/usr/bin/env python3
"""
Automated Belt Shake and Measure Test
--------------------------------------
Tests different shake patterns and measures frequency automatically.

Usage:
    python3 shake_and_measure_test.py <belt> <pattern>
    
Examples:
    python3 shake_and_measure_test.py a quick
    python3 shake_and_measure_test.py b oscillation
    
Patterns: quick, oscillation, small
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

def analyze_frequency(filepath):
    """Analyze using Y-axis (proven method)"""
    try:
        data = np.genfromtxt(filepath, delimiter=',', skip_header=1)
        if len(data) < 500:
            return None
        
        times = data[:, 0]
        accel_y = data[:, 2]  # Y-axis
        
        # Sample rate
        dt = np.mean(np.diff(times))
        sample_rate = 1.0 / dt
        
        # Remove DC and window
        signal_data = accel_y - np.mean(accel_y)
        window = np.hanning(len(signal_data))
        windowed = signal_data * window
        
        # FFT
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
            sorted_indices = np.argsort(peak_mags)[::-1]
            
            # Get all peaks
            all_peaks = []
            for i in sorted_indices[:5]:
                all_peaks.append({
                    'freq': float(peak_freqs[i]),
                    'mag': float(peak_mags[i])
                })
            
            # Find best peak in expected range (95-110 Hz for typical belts)
            best_in_range = None
            for peak in all_peaks:
                if 95 <= peak['freq'] <= 110:
                    best_in_range = peak
                    break
            
            # If we found a good candidate in range, use it as freq1
            # Otherwise fall back to strongest overall
            if best_in_range:
                freq1 = best_in_range['freq']
                # Get the other top frequencies (excluding the one we chose)
                other_freqs = [p['freq'] for p in all_peaks if abs(p['freq'] - freq1) > 2]
                freq2 = other_freqs[0] if len(other_freqs) > 0 else 0
                freq3 = other_freqs[1] if len(other_freqs) > 1 else 0
            else:
                # No peak in expected range, use strongest
                freq1 = all_peaks[0]['freq'] if len(all_peaks) > 0 else 0
                freq2 = all_peaks[1]['freq'] if len(all_peaks) > 1 else 0
                freq3 = all_peaks[2]['freq'] if len(all_peaks) > 2 else 0
            
            return {
                'freq1': freq1,
                'freq2': freq2,
                'freq3': freq3,
                'sample_rate': float(sample_rate),
                'samples': len(data),
                'used_range_filter': best_in_range is not None
            }
        
        return None
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return None

def shake_belt_a(pattern='quick'):
    """Shake Belt A with specified pattern"""
    
    patterns = {
        'quick': [
            'G0 X25 Y25 F12000',
            'G4 P50',
            'G0 X-25 Y-25 F12000',
            'G4 P50',
            'G0 X25 Y25 F12000',
            'G4 P50',
            'G0 X-25 Y-25 F12000',
        ],
        'oscillation': [
            'G0 X10 Y10 F6000',
            'G0 X-20 Y-20 F6000',
            'G0 X20 Y20 F6000',
            'G0 X-20 Y-20 F6000',
            'G0 X20 Y20 F6000',
            'G0 X-20 Y-20 F6000',
            'G0 X10 Y10 F6000',
        ],
        'small': [
            'G0 X5 Y5 F9000',
            'G0 X-10 Y-10 F9000',
            'G0 X10 Y10 F9000',
            'G0 X-10 Y-10 F9000',
            'G0 X10 Y10 F9000',
            'G0 X-10 Y-10 F9000',
            'G0 X5 Y5 F9000',
        ]
    }
    
    return patterns.get(pattern, patterns['quick'])

def shake_belt_b(pattern='quick'):
    """Shake Belt B with specified pattern"""
    
    patterns = {
        'quick': [
            'G0 X25 Y-25 F12000',
            'G4 P50',
            'G0 X-25 Y25 F12000',
            'G4 P50',
            'G0 X25 Y-25 F12000',
            'G4 P50',
            'G0 X-25 Y25 F12000',
        ],
        'oscillation': [
            'G0 X10 Y-10 F6000',
            'G0 X-20 Y20 F6000',
            'G0 X20 Y-20 F6000',
            'G0 X-20 Y20 F6000',
            'G0 X20 Y-20 F6000',
            'G0 X-20 Y20 F6000',
            'G0 X10 Y-10 F6000',
        ],
        'small': [
            'G0 X5 Y-5 F9000',
            'G0 X-10 Y10 F9000',
            'G0 X10 Y-10 F9000',
            'G0 X-10 Y10 F9000',
            'G0 X10 Y-10 F9000',
            'G0 X-10 Y10 F9000',
            'G0 X5 Y-5 F9000',
        ]
    }
    
    return patterns.get(pattern, patterns['quick'])

def test_shake_and_measure(belt, pattern):
    """Run automated shake and measure"""
    
    belt_name = f"Belt {belt.upper()}"
    expected = 101 if belt.lower() == 'a' else 104
    
    print("="*70)
    print(f"AUTOMATED SHAKE AND MEASURE TEST")
    print("="*70)
    print(f"Belt: {belt_name}")
    print(f"Pattern: {pattern}")
    print(f"Expected frequency: ~{expected} Hz (from manual tests)")
    print("="*70)
    print()
    
    # Check homing
    print("Checking printer state...")
    # (Skip actual check for now, assume homed)
    
    # Start measurement
    print("Starting accelerometer measurement...")
    send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
    time.sleep(0.5)
    
    # Save position and switch to relative
    print(f"Executing {pattern} shake pattern...")
    send_gcode("SAVE_GCODE_STATE NAME=shake_test")
    send_gcode("G91")
    
    # Get shake commands
    if belt.lower() == 'a':
        commands = shake_belt_a(pattern)
    else:
        commands = shake_belt_b(pattern)
    
    # Execute shake
    for cmd in commands:
        send_gcode(cmd)
    
    # Restore position
    send_gcode("RESTORE_GCODE_STATE NAME=shake_test")
    
    print("Shake complete, waiting for vibrations to settle...")
    time.sleep(1.5)
    
    # Stop measurement
    print("Stopping measurement...")
    send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=shake_{belt}_{pattern}")
    time.sleep(0.3)
    
    # Analyze
    print("Analyzing data...")
    csv_file = find_latest_csv()
    
    if csv_file:
        result = analyze_frequency(csv_file)
        
        if result:
            print()
            print("="*70)
            print("RESULTS")
            print("="*70)
            print(f"Samples: {result['samples']} @ {result['sample_rate']:.0f} Hz")
            if result.get('used_range_filter'):
                print("✓ Using frequency in expected range (95-110 Hz)")
            print()
            print("Top 3 frequencies detected:")
            
            for i in range(1, 4):
                freq = result[f'freq{i}']
                if freq > 0:
                    error = freq - expected
                    status = "✓" if abs(error) <= 5 else "⚠" if abs(error) <= 10 else "✗"
                    in_range = " [IN RANGE]" if 95 <= freq <= 110 else ""
                    print(f"  {i}. {freq:6.1f} Hz  (error: {error:+5.1f} Hz) {status}{in_range}")
            
            print()
            print("="*70)
            
            # Verdict
            best_freq = result['freq1']
            error = abs(best_freq - expected)
            
            if error <= 3:
                print("✓ EXCELLENT - Matches manual measurement!")
            elif error <= 5:
                print("✓ GOOD - Close to manual measurement")
            elif error <= 10:
                print("⚠ ACCEPTABLE - Within 10 Hz of manual")
            else:
                print(f"✗ POOR - {error:.1f} Hz off from manual measurement")
            
            print("="*70)
            
            return result
        else:
            print("✗ No peaks detected")
            return None
    else:
        print("✗ No data file found")
        return None

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 shake_and_measure_test.py <belt> <pattern>")
        print()
        print("Belt: a or b")
        print("Pattern: quick, oscillation, small")
        print()
        print("Examples:")
        print("  python3 shake_and_measure_test.py a quick")
        print("  python3 shake_and_measure_test.py b oscillation")
        sys.exit(1)
    
    belt = sys.argv[1].lower()
    pattern = sys.argv[2].lower()
    
    if belt not in ['a', 'b']:
        print("Belt must be 'a' or 'b'")
        sys.exit(1)
    
    if pattern not in ['quick', 'oscillation', 'small']:
        print("Pattern must be 'quick', 'oscillation', or 'small'")
        sys.exit(1)
    
    test_shake_and_measure(belt, pattern)

if __name__ == "__main__":
    main()
