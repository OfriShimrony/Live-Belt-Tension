#!/usr/bin/env python3
"""
Belt Frequency Calibration Test
--------------------------------
Tests belt frequency at different positions and movement distances.

This script helps understand:
1. How belt frequency changes with position along the belt path
2. What frequency range to expect for automated measurements
3. Calibration offset between manual pluck and automated shake

Usage:
    python3 belt_calibration_test.py <belt> <position_cm> <movement_mm>
    
Examples:
    python3 belt_calibration_test.py a 10 100
    python3 belt_calibration_test.py a 15 100
    python3 belt_calibration_test.py a 20 100
    python3 belt_calibration_test.py b 15 100
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

def analyze_frequency_full_spectrum(filepath):
    """
    Analyze using Y-axis but show ALL significant peaks
    Don't filter by range - we want to see everything
    """
    try:
        data = np.genfromtxt(filepath, delimiter=',', skip_header=1)
        if len(data) < 500:
            return None
        
        times = data[:, 0]
        accel_y = data[:, 2]  # Y-axis (proven to work best)
        
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
        
        # Belt range (50-200 Hz - wide range to see everything)
        belt_range = (fft_freq >= 50) & (fft_freq <= 200)
        belt_freq = fft_freq[belt_range]
        belt_mag = fft_mag[belt_range]
        
        if len(belt_mag) == 0:
            return None
        
        # Find ALL peaks - lower threshold to see more
        noise_floor = np.percentile(belt_mag, 70)
        threshold = noise_floor * 1.5
        
        peaks, _ = signal.find_peaks(belt_mag, height=threshold, distance=5)
        
        if len(peaks) > 0:
            peak_freqs = belt_freq[peaks]
            peak_mags = belt_mag[peaks]
            sorted_indices = np.argsort(peak_mags)[::-1]
            
            # Get top 10 peaks to see the full picture
            all_peaks = []
            for i in sorted_indices[:10]:
                all_peaks.append({
                    'freq': float(peak_freqs[i]),
                    'mag': float(peak_mags[i]),
                    'rel_mag': float(peak_mags[i] / np.max(peak_mags) * 100)
                })
            
            return {
                'peaks': all_peaks,
                'sample_rate': float(sample_rate),
                'samples': len(data),
                'total_peaks': len(peaks)
            }
        
        return None
        
    except Exception as e:
        print(f"Analysis error: {e}")
        return None

def calibration_test(belt, position_cm, movement_mm):
    """Run calibration test at specific position and movement distance"""
    
    belt_name = f"Belt {belt.upper()}"
    
    print("="*70)
    print("BELT FREQUENCY CALIBRATION TEST")
    print("="*70)
    print(f"Belt: {belt_name}")
    print(f"Position: {position_cm} cm from center")
    print(f"Movement: ±{movement_mm/2:.0f} mm diagonal ({movement_mm} mm total)")
    print("="*70)
    print()
    
    # Calculate movement in X and Y for diagonal
    half_move = movement_mm / 2.0
    
    # IMPORTANT: All movements start from LOWEST value and go to HIGHEST
    # This ensures consistent belt length measurement
    
    if belt.lower() == 'a':
        # Belt A: X+Y diagonal (both increase together)
        # Start at -half, end at +half
        start_x = -half_move
        end_x = half_move
        start_y = -half_move
        end_y = half_move
        print(f"Belt A diagonal: X({start_x:.1f} → {end_x:.1f}) Y({start_y:.1f} → {end_y:.1f})")
    else:
        # Belt B: X-Y diagonal (X increases, Y decreases)
        # Start at X=-half Y=+half, end at X=+half Y=-half
        start_x = -half_move
        end_x = half_move
        start_y = half_move
        end_y = -half_move
        print(f"Belt B diagonal: X({start_x:.1f} → {end_x:.1f}) Y({start_y:.1f} → {end_y:.1f})")
    
    print()
    
    # Position setup
    print("Position setup:")
    print(f"  1. Manually move toolhead to the LOW end (e.g., 10cm from belt center)")
    print(f"  2. The script will move +{movement_mm}mm diagonally from there")
    print(f"  3. This measures the belt across the full {movement_mm}mm range")
    print()
    print(f"  Example: Start at 10cm → Script moves to 20cm → Measures 10-20cm range")
    input("Press ENTER when toolhead is at the LOW starting position...")
    
    # Start measurement
    print()
    print("Starting accelerometer measurement...")
    send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
    time.sleep(0.5)
    
    # Save position and execute shake
    print(f"Executing diagonal movement ({movement_mm}mm in positive direction)...")
    send_gcode("SAVE_GCODE_STATE NAME=calib_test")
    send_gcode("G91")  # Relative positioning
    
    # Movement pattern - ONLY positive direction from starting point
    # This measures the belt from start position to start+movement_mm
    
    if belt.lower() == 'a':
        # Belt A: X+Y diagonal (both increase together)
        # Move forward +100mm
        send_gcode(f"G0 X{movement_mm} Y{movement_mm} F12000")
        send_gcode("G4 P50")
        # Move back -100mm to start
        send_gcode(f"G0 X{-movement_mm} Y{-movement_mm} F12000")
        send_gcode("G4 P50")
        # Move forward again +100mm
        send_gcode(f"G0 X{movement_mm} Y{movement_mm} F12000")
        send_gcode("G4 P50")
        # Return to start -100mm
        send_gcode(f"G0 X{-movement_mm} Y{-movement_mm} F12000")
    else:
        # Belt B: X+Y diagonal but Y goes opposite (X increases, Y decreases)
        # Move forward: +100mm X, -100mm Y
        send_gcode(f"G0 X{movement_mm} Y{-movement_mm} F12000")
        send_gcode("G4 P50")
        # Move back to start: -100mm X, +100mm Y
        send_gcode(f"G0 X{-movement_mm} Y{movement_mm} F12000")
        send_gcode("G4 P50")
        # Move forward again
        send_gcode(f"G0 X{movement_mm} Y{-movement_mm} F12000")
        send_gcode("G4 P50")
        # Return to start
        send_gcode(f"G0 X{-movement_mm} Y{movement_mm} F12000")
    
    send_gcode("RESTORE_GCODE_STATE NAME=calib_test")
    
    print("Shake complete, waiting for vibrations to settle...")
    time.sleep(1.5)
    
    # Stop measurement
    print("Stopping measurement...")
    send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=calib_{belt}_{position_cm}cm_{movement_mm}mm")
    time.sleep(0.3)
    
    # Analyze
    print("Analyzing data...")
    csv_file = find_latest_csv()
    
    if csv_file:
        result = analyze_frequency_full_spectrum(csv_file)
        
        if result:
            print()
            print("="*70)
            print("RESULTS - ALL DETECTED PEAKS")
            print("="*70)
            print(f"Samples: {result['samples']} @ {result['sample_rate']:.0f} Hz")
            print(f"Total peaks found: {result['total_peaks']}")
            print()
            print("Rank  Frequency    Rel.Mag   Notes")
            print("-" * 70)
            
            for i, peak in enumerate(result['peaks'], 1):
                freq = peak['freq']
                rel_mag = peak['rel_mag']
                
                # Notes about this frequency
                notes = []
                if 95 <= freq <= 115:
                    notes.append("⭐ EXPECTED BELT RANGE")
                if 50 <= freq <= 75:
                    notes.append("Possible sub-harmonic or frame resonance")
                if freq > 150:
                    notes.append("Possible harmonic or movement noise")
                
                note_str = " | ".join(notes) if notes else ""
                
                print(f" {i:2d}.  {freq:6.1f} Hz   {rel_mag:5.1f}%   {note_str}")
            
            print()
            print("="*70)
            
            # Save to CSV for later analysis
            return {
                'belt': belt,
                'position_cm': position_cm,
                'movement_mm': movement_mm,
                'peaks': result['peaks'],
                'sample_rate': result['sample_rate'],
                'samples': result['samples']
            }
        else:
            print("✗ No peaks detected")
            return None
    else:
        print("✗ No data file found")
        return None

def save_calibration_data(results, filename='belt_calibration_data.csv'):
    """Save calibration results to CSV"""
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'belt',
            'position_cm',
            'movement_mm',
            'rank',
            'frequency_hz',
            'relative_magnitude_pct',
            'sample_rate',
            'samples'
        ])
        
        # Data
        for r in results:
            for i, peak in enumerate(r['peaks'], 1):
                writer.writerow([
                    r['belt'],
                    r['position_cm'],
                    r['movement_mm'],
                    i,
                    peak['freq'],
                    peak['rel_mag'],
                    r['sample_rate'],
                    r['samples']
                ])
    
    print(f"\n✓ Calibration data saved to: {filename}")

def main():
    if len(sys.argv) < 4:
        print("Usage: python3 belt_calibration_test.py <belt> <position_cm> <movement_mm>")
        print()
        print("Parameters:")
        print("  belt: a or b")
        print("  position_cm: Position along belt (10, 15, 20, etc.)")
        print("  movement_mm: Total diagonal movement (e.g., 100)")
        print()
        print("Example test sequence:")
        print("  python3 belt_calibration_test.py a 10 100")
        print("  python3 belt_calibration_test.py a 15 100")
        print("  python3 belt_calibration_test.py a 20 100")
        print()
        print("Then repeat for belt b:")
        print("  python3 belt_calibration_test.py b 10 100")
        print("  python3 belt_calibration_test.py b 15 100")
        print("  python3 belt_calibration_test.py b 20 100")
        sys.exit(1)
    
    belt = sys.argv[1].lower()
    position_cm = int(sys.argv[2])
    movement_mm = int(sys.argv[3])
    
    if belt not in ['a', 'b']:
        print("Belt must be 'a' or 'b'")
        sys.exit(1)
    
    result = calibration_test(belt, position_cm, movement_mm)
    
    # Optionally save
    if result:
        save_choice = input("\nSave this result to calibration file? (y/n): ").strip().lower()
        if save_choice == 'y':
            # Load existing or create new
            filename = 'belt_calibration_data.csv'
            results = [result]
            
            # Check if file exists and load previous data
            if os.path.exists(filename):
                print(f"Appending to existing {filename}")
                # For now, just append (could improve to merge)
            
            save_calibration_data(results, filename)

if __name__ == "__main__":
    main()
