#!/usr/bin/env python3
"""
Quick Belt Frequency Diagnostic
--------------------------------
Run this after a shake to see what's really happening with the frequencies.
"""

import numpy as np
from scipy import signal
import os

def find_latest_csvs(count=3):
    """Find most recent accelerometer data files"""
    data_dir = "/tmp"
    files = []
    for filename in os.listdir(data_dir):
        if filename.startswith("adxl345-") and filename.endswith(".csv"):
            filepath = os.path.join(data_dir, filename)
            files.append((filepath, os.path.getmtime(filepath)))
    
    if files:
        files.sort(key=lambda x: x[1], reverse=True)
        return [f[0] for f in files[:count]]
    return []

def quick_analysis():
    """Quick diagnostic of belt frequency"""
    files = find_latest_csvs(count=2)
    if not files:
        print("No data files found!")
        return
    
    print(f"Found {len(files)} recent measurement(s)\n")
    
    for file_num, filepath in enumerate(files, 1):
        print(f"{'='*70}")
        print(f"File {file_num}: {os.path.basename(filepath)}")
        print(f"{'='*70}")
        
        # Load data
        data = np.genfromtxt(filepath, delimiter=',', skip_header=0)
        times = data[:, 0]
        accel_x = data[:, 1]
        accel_y = data[:, 2]
        
        # Basic info
        dt = np.mean(np.diff(times))
        sample_rate = 1.0 / dt
        
        print(f"Sample rate: {sample_rate:.1f} Hz")
        print(f"Duration: {times[-1] - times[0]:.2f} seconds")
        print(f"Samples: {len(data)}")
        print()
        
        # Analyze both axes
        for axis_name, accel_data in [('X (Belt A)', accel_x), ('Y (Belt B)', accel_y)]:
            print(f"--- {axis_name} ---")
        
        # Remove DC
        signal_data = accel_data - np.mean(accel_data)
        
        # Apply window
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
        
        # Find ALL peaks above noise
        noise_floor = np.percentile(belt_mag, 75)
        threshold = noise_floor * 2
        
        peaks, _ = signal.find_peaks(belt_mag, height=threshold, distance=10)
        
        if len(peaks) > 0:
            peak_freqs = belt_freq[peaks]
            peak_mags = belt_mag[peaks]
            
            # Sort by magnitude
            sorted_indices = np.argsort(peak_mags)[::-1]
            
            print(f"Found {len(peaks)} peaks above noise:")
            for i in sorted_indices[:5]:  # Show top 5
                freq = peak_freqs[i]
                mag = peak_mags[i]
                rel_mag = mag / np.max(peak_mags) * 100
                print(f"  {freq:6.1f} Hz  (magnitude: {mag:8.0f}, {rel_mag:5.1f}%)")
            
            # Check for harmonics
            strongest_freq = peak_freqs[sorted_indices[0]]
            print(f"\nStrongest peak: {strongest_freq:.1f} Hz")
            print("Checking for harmonics:")
            print(f"  2x = {strongest_freq*2:.1f} Hz")
            print(f"  3x = {strongest_freq*3:.1f} Hz")
            print(f"  0.5x = {strongest_freq*0.5:.1f} Hz")
            print(f"  0.33x = {strongest_freq*0.33:.1f} Hz")
        else:
            print("No significant peaks found!")
        
        print()
    
    print()  # Spacing between files

if __name__ == "__main__":
    quick_analysis()
