#!/usr/bin/env python3
"""
Simple Belt Tension Tuner - Shake on Demand
--------------------------------------------
Position at 15cm reference point, press ENTER to measure.
Adjust tension between measurements.

Usage:
    python3 simple_belt_tuner.py <belt>
    
Examples:
    python3 simple_belt_tuner.py a
    python3 simple_belt_tuner.py b
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

def analyze_frequency_with_all_peaks(filepath):
    """Analyze and return top 5 peaks for user to see"""
    try:
        data = np.genfromtxt(filepath, delimiter=',', skip_header=1)
        if len(data) < 500:
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
        
        # Belt range (50-200 Hz)
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
            
            # Get top 5 peaks
            top_peaks = []
            for i in sorted_indices[:5]:
                top_peaks.append({
                    'freq': float(peak_freqs[i]),
                    'mag': float(peak_mags[i]),
                    'rel_mag': float(peak_mags[i] / np.max(peak_mags) * 100)
                })
            
            return {
                'peaks': top_peaks,
                'sample_rate': float(sample_rate),
                'samples': len(data)
            }
        
        return None
        
    except Exception as e:
        return None

def shake_belt(belt, shake_distance=10, speed=3000):
    """
    Perform a gentle diagonal shake
    
    Args:
        shake_distance: Movement distance in mm (default 10mm - much smaller)
        speed: Movement speed in mm/min (default 3000 = 50mm/s - much slower)
    """
    
    # Gentle shake pattern - small movement, slow speed
    if belt.lower() == 'a':
        # Belt A: X-Y diagonal (opposite directions)
        send_gcode("G91")  # Relative
        send_gcode(f"G0 X{shake_distance} Y-{shake_distance} F{speed}")
        send_gcode("G4 P100")
        send_gcode(f"G0 X-{shake_distance*2} Y{shake_distance*2} F{speed}")
        send_gcode("G4 P100")
        send_gcode(f"G0 X{shake_distance*2} Y-{shake_distance*2} F{speed}")
        send_gcode("G4 P100")
        send_gcode(f"G0 X-{shake_distance} Y{shake_distance} F{speed}")
        send_gcode("G90")  # Back to absolute
    else:
        # Belt B: X+Y diagonal (same direction)
        send_gcode("G91")  # Relative
        send_gcode(f"G0 X{shake_distance} Y{shake_distance} F{speed}")
        send_gcode("G4 P100")
        send_gcode(f"G0 X-{shake_distance*2} Y-{shake_distance*2} F{speed}")
        send_gcode("G4 P100")
        send_gcode(f"G0 X{shake_distance*2} Y{shake_distance*2} F{speed}")
        send_gcode("G4 P100")
        send_gcode(f"G0 X-{shake_distance} Y-{shake_distance} F{speed}")
        send_gcode("G90")  # Back to absolute

def simple_tuner(belt):
    """Interactive belt tuning - shake on demand"""
    
    belt_name = f"Belt {belt.upper()}"
    
    print("="*70)
    print("SIMPLE BELT TENSION TUNER")
    print("="*70)
    print(f"Belt: {belt_name}")
    print()
    print("Setup:")
    print("  1. Position toolhead at X175 Y98 (15cm reference point)")
    print("  2. Press ENTER to shake and measure")
    print("  3. Adjust belt tension as needed")
    print("  4. Press ENTER again for new reading")
    print("  5. Type 'done' when finished")
    print()
    print("Target: 100-115 Hz")
    print("="*70)
    print()
    
    input("Press ENTER when positioned at X175 Y98...")
    
    measurement_num = 1
    history = []
    
    print()
    print("="*70)
    print("#    Top 5 Frequencies (Hz)                           Best Guess")
    print("-"*70)
    
    while True:
        user_input = input(f"\n[{measurement_num}] Press ENTER to measure (or 'done'): ").strip().lower()
        
        if user_input in ['done', 'd', 'quit', 'q']:
            break
        
        # Start measurement
        send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
        time.sleep(0.3)
        
        # Shake the belt
        print("  Shaking gently...", end='', flush=True)
        shake_belt(belt)
        
        # Wait longer for vibrations to develop and settle (slower movement needs more time)
        time.sleep(1.5)
        
        # Stop measurement
        send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=simple_{belt}_{measurement_num}")
        time.sleep(0.3)
        
        # Analyze
        csv_file = find_latest_csv()
        if csv_file:
            result = analyze_frequency_with_all_peaks(csv_file)
            
            if result and result['peaks']:
                peaks = result['peaks']
                
                # Show all peaks
                freq_list = " | ".join([f"{p['freq']:5.1f}" for p in peaks])
                
                # Determine best guess: strongest peak in 90-120 Hz range, or just strongest
                in_range = [p for p in peaks if 90 <= p['freq'] <= 120]
                if in_range:
                    best = in_range[0]['freq']  # Already sorted by magnitude
                    marker = "✓"
                else:
                    best = peaks[0]['freq']
                    marker = "⚠" if best > 120 else "⬇" if best < 90 else "?"
                
                print(f"\r {measurement_num:2d}  {freq_list:45s}   {best:6.1f} Hz {marker}")
                
                history.append({
                    'num': measurement_num,
                    'best': best,
                    'peaks': peaks
                })
                
                measurement_num += 1
            else:
                print("\r  ✗ No clear peaks detected")
        else:
            print("\r  ✗ No data file found")
    
    # Summary
    if history:
        print()
        print("="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Total measurements: {len(history)}")
        
        best_freqs = [h['best'] for h in history]
        print(f"\nBest guess frequencies:")
        print(f"  Latest:  {best_freqs[-1]:.1f} Hz")
        print(f"  Average: {np.mean(best_freqs):.1f} Hz")
        print(f"  Std Dev: {np.std(best_freqs):.1f} Hz")
        print(f"  Range:   {np.min(best_freqs):.1f} - {np.max(best_freqs):.1f} Hz")
        
        if np.std(best_freqs) > 10:
            print("\n⚠ High variation - belt tension may be inconsistent")
        elif 100 <= np.mean(best_freqs) <= 115:
            print("\n✓ Belt tension looks good!")
        
        print("="*70)
    
    print("\n✓ Done")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 simple_belt_tuner.py <belt>")
        print()
        print("Examples:")
        print("  python3 simple_belt_tuner.py a")
        print("  python3 simple_belt_tuner.py b")
        sys.exit(1)
    
    belt = sys.argv[1].lower()
    
    if belt not in ['a', 'b']:
        print("Belt must be 'a' or 'b'")
        sys.exit(1)
    
    simple_tuner(belt)

if __name__ == "__main__":
    main()
