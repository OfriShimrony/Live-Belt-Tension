#!/usr/bin/env python3
"""
ADXL345 Data Collection with FFT Analysis
-----------------------------------------
Collects accelerometer data and performs FFT to find dominant frequencies.
This is the core of belt tension detection!

Usage:
    python3 adxl_fft_test.py

Requirements:
    - Klipper running with ADXL345 configured
    - Moonraker running
    - NumPy and SciPy installed: pip install numpy scipy
"""

import requests
import time
import sys
import os
import numpy as np
from scipy import signal
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

# Moonraker API endpoint
MOONRAKER_URL = "http://localhost:7125"

def test_connection():
    """Test connection to Moonraker"""
    try:
        response = requests.get(f"{MOONRAKER_URL}/server/info", timeout=5)
        if response.status_code == 200:
            print("✓ Connected to Moonraker")
            return True
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
        print(f"✗ Error: {e}")
        return False

def find_data_file():
    """Find the most recent accelerometer data file"""
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

def collect_data(duration=5):
    """Collect accelerometer data for specified duration"""
    print(f"\n--- Collecting {duration}-second sample ---")
    
    # Start measurement
    if not send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345"):
        print("✗ Failed to start measurement")
        return None
    
    print("✓ Measurement started")
    print(f"  Collecting data for {duration} seconds...")
    print("  (Try plucking a belt now to see its frequency!)")
    
    time.sleep(duration)
    
    # Stop measurement
    if not send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345 NAME=fft_test"):
        print("✗ Failed to stop measurement")
        return None
    
    print("✓ Measurement complete")
    time.sleep(0.5)
    
    # Find and read the data file
    datafile = find_data_file()
    if not datafile:
        print("✗ Couldn't find data file")
        return None
    
    print(f"✓ Found data: {datafile}")
    return datafile

def parse_csv_data(filepath):
    """Parse CSV data file into numpy arrays"""
    try:
        data = np.genfromtxt(filepath, delimiter=',', skip_header=0)
        
        if len(data) == 0:
            print("✗ No data in file")
            return None
        
        # Extract columns: time, x, y, z
        times = data[:, 0]
        accel_x = data[:, 1]
        accel_y = data[:, 2]
        accel_z = data[:, 3]
        
        # Calculate sampling rate
        dt = np.mean(np.diff(times))
        sample_rate = 1.0 / dt
        
        print(f"\n--- Data Info ---")
        print(f"  Samples: {len(times)}")
        print(f"  Duration: {times[-1] - times[0]:.2f} seconds")
        print(f"  Sample rate: {sample_rate:.1f} Hz")
        
        return {
            'times': times,
            'x': accel_x,
            'y': accel_y,
            'z': accel_z,
            'sample_rate': sample_rate
        }
        
    except Exception as e:
        print(f"✗ Error parsing data: {e}")
        return None

def perform_fft(data, axis='x'):
    """Perform FFT analysis on accelerometer data"""
    print(f"\n--- FFT Analysis ({axis.upper()}-axis) ---")
    
    # Get the data for specified axis
    signal_data = data[axis]
    sample_rate = data['sample_rate']
    
    # Remove DC component (mean)
    signal_data = signal_data - np.mean(signal_data)
    
    # Apply window function to reduce spectral leakage
    window = np.hanning(len(signal_data))
    signal_windowed = signal_data * window
    
    # Perform FFT
    fft_result = np.fft.rfft(signal_windowed)
    fft_freq = np.fft.rfftfreq(len(signal_windowed), 1.0/sample_rate)
    
    # Calculate magnitude (power spectral density)
    fft_magnitude = np.abs(fft_result)
    
    # Find peak frequencies (typical belt range: 80-140 Hz)
    belt_range = (fft_freq >= 50) & (fft_freq <= 200)
    belt_freq = fft_freq[belt_range]
    belt_mag = fft_magnitude[belt_range]
    
    if len(belt_mag) > 0:
        # Find top 3 peaks
        peak_indices = signal.find_peaks(belt_mag, height=np.max(belt_mag)*0.3)[0]
        
        if len(peak_indices) > 0:
            # Sort by magnitude
            sorted_peaks = sorted(peak_indices, key=lambda i: belt_mag[i], reverse=True)
            
            print(f"\n  Top frequencies found:")
            for i, peak_idx in enumerate(sorted_peaks[:3], 1):
                freq = belt_freq[peak_idx]
                magnitude = belt_mag[peak_idx]
                print(f"    {i}. {freq:.1f} Hz (magnitude: {magnitude:.1f})")
            
            return {
                'frequencies': fft_freq,
                'magnitudes': fft_magnitude,
                'peak_freq': belt_freq[sorted_peaks[0]] if sorted_peaks else 0,
                'belt_freq': belt_freq,
                'belt_mag': belt_mag
            }
    
    return None

def save_plot(fft_data, axis='x', filename='/tmp/fft_plot.png'):
    """Save FFT plot to file"""
    try:
        plt.figure(figsize=(12, 6))
        
        # Plot full spectrum
        plt.subplot(1, 2, 1)
        plt.plot(fft_data['frequencies'], fft_data['magnitudes'])
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Magnitude')
        plt.title(f'Full Frequency Spectrum ({axis.upper()}-axis)')
        plt.grid(True)
        plt.xlim(0, 300)
        
        # Plot belt frequency range
        plt.subplot(1, 2, 2)
        plt.plot(fft_data['belt_freq'], fft_data['belt_mag'], 'b-', linewidth=2)
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Magnitude')
        plt.title('Belt Frequency Range (50-200 Hz)')
        plt.grid(True)
        
        # Mark peak
        if fft_data['peak_freq'] > 0:
            plt.axvline(fft_data['peak_freq'], color='r', linestyle='--', 
                       label=f'Peak: {fft_data["peak_freq"]:.1f} Hz')
            plt.legend()
        
        plt.tight_layout()
        plt.savefig(filename, dpi=100)
        plt.close()
        
        print(f"\n✓ Plot saved to: {filename}")
        return True
        
    except Exception as e:
        print(f"✗ Error saving plot: {e}")
        return False

def main():
    print("="*60)
    print("ADXL345 FFT Analysis Test")
    print("="*60)
    
    # Check dependencies
    print("\nChecking dependencies...")
    print("  ✓ NumPy available")
    print("  ✓ SciPy available")
    print("  ✓ Matplotlib available")
    
    # Test connection
    if not test_connection():
        sys.exit(1)
    
    try:
        # Collect data
        datafile = collect_data(duration=5)
        if not datafile:
            sys.exit(1)
        
        # Parse data
        data = parse_csv_data(datafile)
        if not data:
            sys.exit(1)
        
        # Perform FFT on X axis (most relevant for belt A on CoreXY)
        fft_result = perform_fft(data, axis='x')
        
        if fft_result:
            # Save plot
            save_plot(fft_result, axis='x')
            
            print("\n" + "="*60)
            print("✓ FFT Analysis Complete!")
            print("\nWhat this means:")
            print("- The peak frequency shown is the dominant vibration")
            print("- For belt tension, look for frequencies 80-140 Hz")
            print("- Higher frequency = tighter belt")
            print("- Lower frequency = looser belt")
            print("\nNext steps:")
            print("- Try plucking a belt and run this again")
            print("- We can now build the live tuner interface!")
        else:
            print("\n⚠ No clear peaks found in belt frequency range")
            print("  Try plucking a belt while collecting data")
        
    except KeyboardInterrupt:
        print("\n\n✓ Interrupted by user")
        send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345 NAME=stop")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
