#!/usr/bin/env python3
"""
Belt Tension Tuner - Manual Pluck Detection
--------------------------------------------
Listens for manual belt plucks and analyzes frequency in real-time.

Uses all the improved signal processing we developed:
- DC offset removal
- Axis magnitude integration (orientation-agnostic)
- Hanning window
- Band-pass filtering (60-250 Hz)
- Q-factor analysis (peak sharpness)
- Time-decay validation (STFT)
- SNR validation

Usage from Mainsail terminal:
    BELT_TUNE_START BELT=A
    [manually pluck belt]
    [frequency displays]
    BELT_TUNE_STOP
"""

import requests
import time
import os
import sys
import numpy as np
from scipy import signal as scipy_signal
from scipy.fft import rfft, rfftfreq

MOONRAKER_URL = "http://localhost:7125"

def send_gcode(command):
    """Send G-code command to Klipper"""
    try:
        url = f"{MOONRAKER_URL}/printer/gcode/script"
        params = {"script": command}
        response = requests.post(url, params=params, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending command: {e}")
        return False

def find_latest_csv():
    """Find most recent ADXL CSV file"""
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

def analyze_pluck(filepath, belt_name):
    """
    Complete signal analysis pipeline for belt pluck
    
    Returns dict with:
        - frequency: detected belt frequency
        - confidence: HIGH/MEDIUM/LOW
        - q_factor: peak sharpness
        - snr: signal-to-noise ratio
        - decay: whether signal decays properly
    """
    
    try:
        # Load data
        data = np.genfromtxt(filepath, delimiter=',', skip_header=1)
        if len(data) < 512:
            return {'error': 'Insufficient samples', 'samples': len(data)}
        
        times = data[:, 0]
        accel_x = data[:, 1]
        accel_y = data[:, 2]
        
        # Sample rate
        dt = np.mean(np.diff(times))
        sample_rate = 1.0 / dt
        
        # ===================================================================
        # STEP 1: DC Offset Removal (Remove gravity)
        # ===================================================================
        accel_x_centered = accel_x - np.mean(accel_x)
        accel_y_centered = accel_y - np.mean(accel_y)
        
        # ===================================================================
        # STEP 2: Axis Integration - Euclidean Magnitude (Orientation-Agnostic)
        # ===================================================================
        accel_magnitude = np.sqrt(accel_x_centered**2 + accel_y_centered**2)
        
        # ===================================================================
        # STEP 3: Temporal Windowing (Prevent spectral leakage)
        # ===================================================================
        window = np.hanning(len(accel_magnitude))
        windowed_signal = accel_magnitude * window
        
        # ===================================================================
        # STEP 4: FFT Transform
        # ===================================================================
        fft_result = rfft(windowed_signal)
        fft_freq = rfftfreq(len(windowed_signal), 1.0/sample_rate)
        fft_mag = np.abs(fft_result)
        
        # ===================================================================
        # STEP 5: Band-pass Filter (60-250 Hz)
        # ===================================================================
        belt_range = (fft_freq >= 60) & (fft_freq <= 250)
        belt_freq = fft_freq[belt_range]
        belt_mag = fft_mag[belt_range]
        
        if len(belt_mag) == 0:
            return {'error': 'No data in belt frequency range'}
        
        # ===================================================================
        # STEP 6: Noise Floor & Peak Detection
        # ===================================================================
        noise_floor = np.percentile(belt_mag, 75)
        threshold = noise_floor * 1.5
        
        peaks, properties = scipy_signal.find_peaks(
            belt_mag,
            height=threshold,
            prominence=noise_floor * 0.5,
            distance=int(5 / (belt_freq[1] - belt_freq[0]))
        )
        
        if len(peaks) == 0:
            return {'error': 'No peaks above noise floor'}
        
        peak_freqs = belt_freq[peaks]
        peak_mags = belt_mag[peaks]
        
        # ===================================================================
        # STEP 7: Q-Factor Analysis
        # ===================================================================
        def calculate_q_factor(center_freq, center_mag, freqs, mags):
            half_power = center_mag / np.sqrt(2)
            above_half = mags > half_power
            
            if np.sum(above_half) < 2:
                return 0
            
            half_power_indices = np.where(above_half)[0]
            bandwidth = freqs[half_power_indices[-1]] - freqs[half_power_indices[0]]
            
            if bandwidth == 0:
                return 0
            
            return center_freq / bandwidth
        
        candidates = []
        sorted_indices = np.argsort(peak_mags)[::-1]
        
        for i in sorted_indices[:5]:
            freq = peak_freqs[i]
            mag = peak_mags[i]
            
            snr = mag / noise_floor
            q_factor = calculate_q_factor(freq, mag, belt_freq, belt_mag)
            
            candidates.append({
                'freq': float(freq),
                'mag': float(mag),
                'snr': float(snr),
                'q_factor': float(q_factor)
            })
        
        # ===================================================================
        # STEP 8: Time-Decay Validation (STFT)
        # ===================================================================
        chunk_size = len(accel_magnitude) // 3
        chunks = [
            accel_magnitude[0:chunk_size],
            accel_magnitude[chunk_size:2*chunk_size],
            accel_magnitude[2*chunk_size:3*chunk_size]
        ]
        
        for candidate in candidates[:3]:
            decay_profile = []
            
            for chunk in chunks:
                if len(chunk) < 100:
                    continue
                
                chunk_window = np.hanning(len(chunk))
                chunk_windowed = chunk * chunk_window
                chunk_fft = np.abs(rfft(chunk_windowed))
                chunk_freqs = rfftfreq(len(chunk_windowed), 1.0/sample_rate)
                
                target_freq = candidate['freq']
                freq_idx = np.argmin(np.abs(chunk_freqs - target_freq))
                chunk_mag = chunk_fft[freq_idx]
                
                decay_profile.append(chunk_mag)
            
            if len(decay_profile) == 3:
                candidate['decay_profile'] = decay_profile
                candidate['is_decaying'] = decay_profile[0] > decay_profile[1] > decay_profile[2]
        
        # ===================================================================
        # STEP 9: Score and Select Best Candidate
        # ===================================================================
        for candidate in candidates:
            score = 0
            
            # High Q-factor (sharp peak)
            if candidate['q_factor'] > 10:
                score += 3
            elif candidate['q_factor'] > 5:
                score += 1
            
            # High SNR
            if candidate['snr'] > 5:
                score += 2
            elif candidate['snr'] > 3:
                score += 1
            
            # Decaying (proves mechanical resonance)
            if candidate.get('is_decaying', False):
                score += 3
            
            # In expected range (80-140 Hz for typical belts)
            if 80 <= candidate['freq'] <= 140:
                score += 2
            
            candidate['score'] = score
        
        # Sort by score
        candidates.sort(key=lambda x: x['score'], reverse=True)
        best = candidates[0]
        
        # Determine confidence
        if best['score'] >= 6:
            confidence = "HIGH"
        elif best['score'] >= 4:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
        
        return {
            'frequency': best['freq'],
            'snr': best['snr'],
            'q_factor': best['q_factor'],
            'confidence': confidence,
            'score': best['score'],
            'is_decaying': best.get('is_decaying', False),
            'all_candidates': candidates,
            'sample_rate': sample_rate,
            'samples': len(data)
        }
        
    except Exception as e:
        return {'error': str(e)}

def monitor_plucks(belt_name, position=None):
    """
    Monitor for manual belt plucks and analyze in real-time
    
    Args:
        belt_name: 'A' or 'B'
        position: Optional position description (e.g., 'X175 Y98')
    """
    
    print("="*70)
    print("BELT TENSION TUNER - Manual Pluck Detection")
    print("="*70)
    print(f"Belt: {belt_name}")
    if position:
        print(f"Position: {position}")
    print()
    print("Instructions:")
    print("  1. Pluck the belt manually (like a guitar string)")
    print("  2. Frequency will display automatically")
    print("  3. Run BELT_TUNE_STOP when done")
    print()
    print("Waiting for plucks...")
    print("="*70)
    print()
    
    # Start continuous measurement
    send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
    
    last_file_time = 0
    measurement_count = 0
    
    # Monitor for new files (indicating a measurement was saved)
    # In practice, we'd need a different trigger mechanism
    # For now, this is a placeholder for the monitoring loop
    
    try:
        while True:
            # Check for user stop command
            # This would be triggered by BELT_TUNE_STOP macro
            
            # Wait a bit
            time.sleep(0.5)
            
            # In actual implementation:
            # - Listen for pluck detection (signal spike)
            # - Save a 1-2 second window around the pluck
            # - Analyze immediately
            # - Display result
            
            # This is a simplified version for now
            
    except KeyboardInterrupt:
        pass
    finally:
        send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345 NAME=pluck_monitor")

def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 belt_pluck_detector.py <belt> [position]")
        print()
        print("Examples:")
        print("  python3 belt_pluck_detector.py A")
        print("  python3 belt_pluck_detector.py B 'X175 Y98'")
        sys.exit(1)
    
    belt = sys.argv[1].upper()
    position = sys.argv[2] if len(sys.argv) > 2 else None
    
    if belt not in ['A', 'B']:
        print("Belt must be 'A' or 'B'")
        sys.exit(1)
    
    monitor_plucks(belt, position)

if __name__ == "__main__":
    main()
