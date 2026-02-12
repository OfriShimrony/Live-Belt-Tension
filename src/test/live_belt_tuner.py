#!/usr/bin/env python3
"""
Live Belt Tension Tuner
-----------------------
Real-time belt frequency display - like a guitar tuner!
Shows live frequency updates as you adjust belt tension.

Usage:
    python3 live_belt_tuner.py

Controls:
    Ctrl+C to stop

Requirements:
    - Klipper with ADXL345
    - NumPy, SciPy: pip3 install numpy scipy
"""

import requests
import time
import sys
import os
import numpy as np
from scipy import signal
import threading
import queue

# Configuration
MOONRAKER_URL = "http://localhost:7125"
MEASUREMENT_DURATION = 2.0  # Seconds per measurement
TARGET_FREQ_MIN = 100  # Hz - typical belt range
TARGET_FREQ_MAX = 140  # Hz

class LiveBeltTuner:
    def __init__(self):
        self.running = False
        self.data_queue = queue.Queue()
        self.latest_frequency = None
        self.measurement_count = 0
        
    def test_connection(self):
        """Test Moonraker connection"""
        try:
            response = requests.get(f"{MOONRAKER_URL}/server/info", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def send_gcode(self, command):
        """Send G-code command"""
        try:
            url = f"{MOONRAKER_URL}/printer/gcode/script"
            params = {"script": command}
            response = requests.post(url, params=params, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def find_latest_csv(self):
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
    
    def analyze_data(self, filepath):
        """Quick FFT analysis to find belt frequency"""
        try:
            # Load data
            data = np.genfromtxt(filepath, delimiter=',', skip_header=0)
            if len(data) < 100:
                return None
            
            # Extract X-axis acceleration
            accel_x = data[:, 1]
            
            # Calculate sample rate
            times = data[:, 0]
            dt = np.mean(np.diff(times))
            sample_rate = 1.0 / dt
            
            # Remove DC and apply window
            signal_data = accel_x - np.mean(accel_x)
            window = np.hanning(len(signal_data))
            signal_windowed = signal_data * window
            
            # FFT
            fft_result = np.fft.rfft(signal_windowed)
            fft_freq = np.fft.rfftfreq(len(signal_windowed), 1.0/sample_rate)
            fft_magnitude = np.abs(fft_result)
            
            # Focus on belt frequency range (50-200 Hz)
            belt_range = (fft_freq >= 50) & (fft_freq <= 200)
            belt_freq = fft_freq[belt_range]
            belt_mag = fft_magnitude[belt_range]
            
            if len(belt_mag) > 0:
                # Find peak
                peak_indices = signal.find_peaks(belt_mag, height=np.max(belt_mag)*0.3)[0]
                if len(peak_indices) > 0:
                    sorted_peaks = sorted(peak_indices, key=lambda i: belt_mag[i], reverse=True)
                    peak_freq = belt_freq[sorted_peaks[0]]
                    peak_magnitude = belt_mag[sorted_peaks[0]]
                    
                    return {
                        'frequency': peak_freq,
                        'magnitude': peak_magnitude,
                        'sample_rate': sample_rate,
                        'samples': len(data)
                    }
            
            return None
            
        except Exception as e:
            return None
    
    def measurement_loop(self):
        """Background thread that continuously collects and analyzes data"""
        while self.running:
            try:
                # Start measurement
                self.send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
                
                # Wait for data collection
                time.sleep(MEASUREMENT_DURATION)
                
                # Stop measurement with unique name
                measurement_name = f"live_{self.measurement_count}"
                self.send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME={measurement_name}")
                self.measurement_count += 1
                
                # Give time to write file
                time.sleep(0.3)
                
                # Find and analyze data
                csv_file = self.find_latest_csv()
                if csv_file:
                    result = self.analyze_data(csv_file)
                    if result:
                        self.data_queue.put(result)
                
            except Exception as e:
                if self.running:  # Only print if not stopping
                    print(f"\n⚠ Measurement error: {e}")
                time.sleep(0.5)
    
    def draw_frequency_bar(self, frequency):
        """Draw visual frequency indicator"""
        # Create bar graph
        bar_width = 50
        
        # Calculate position in target range
        if frequency < TARGET_FREQ_MIN:
            position = 0
            status = "TOO LOOSE"
            color = "⬇️ "
        elif frequency > TARGET_FREQ_MAX:
            position = bar_width
            status = "TOO TIGHT"
            color = "⬆️ "
        else:
            # Within target range
            range_width = TARGET_FREQ_MAX - TARGET_FREQ_MIN
            position = int(((frequency - TARGET_FREQ_MIN) / range_width) * bar_width)
            status = "✓ GOOD"
            color = "✓ "
        
        # Draw the bar
        bar = ['─'] * bar_width
        if 0 <= position < bar_width:
            bar[position] = '█'
        
        bar_str = ''.join(bar)
        
        return f"{color}{bar_str} {status}"
    
    def display_loop(self):
        """Main display loop - shows live frequency updates"""
        print("\n" + "="*70)
        print("LIVE BELT TENSION TUNER")
        print("="*70)
        print("\nStarting measurements...")
        print("Pluck your belt and watch the frequency!\n")
        print(f"Target range: {TARGET_FREQ_MIN}-{TARGET_FREQ_MAX} Hz")
        print("Press Ctrl+C to stop\n")
        print("─"*70)
        
        last_update = time.time()
        
        while self.running:
            try:
                # Get latest result (non-blocking with timeout)
                try:
                    result = self.data_queue.get(timeout=0.5)
                    
                    # Update display
                    freq = result['frequency']
                    magnitude = result['magnitude']
                    
                    # Clear previous line and print new data
                    print(f"\r", end='')
                    print(f"Frequency: {freq:6.1f} Hz  |  ", end='')
                    print(self.draw_frequency_bar(freq), end='')
                    print(f"  |  Samples: {result['samples']}", end='', flush=True)
                    
                    last_update = time.time()
                    
                except queue.Empty:
                    # Show waiting indicator if no update for a while
                    if time.time() - last_update > 3:
                        print(f"\rWaiting for data... (pluck belt to see frequency)", end='', flush=True)
                
            except KeyboardInterrupt:
                break
        
        print("\n\n" + "─"*70)
    
    def run(self):
        """Main run function"""
        # Test connection
        print("Connecting to Klipper...")
        if not self.test_connection():
            print("✗ Cannot connect to Moonraker")
            print(f"  Make sure it's running at: {MOONRAKER_URL}")
            return False
        
        print("✓ Connected")
        
        # Start measurement thread
        self.running = True
        measurement_thread = threading.Thread(target=self.measurement_loop, daemon=True)
        measurement_thread.start()
        
        try:
            # Run display loop
            self.display_loop()
        except KeyboardInterrupt:
            pass
        finally:
            # Clean shutdown
            print("\n\nStopping...")
            self.running = False
            
            # Stop any ongoing measurement
            self.send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345 NAME=stop")
            
            # Wait for thread to finish
            measurement_thread.join(timeout=2)
            
            print("✓ Stopped")
            print("\n" + "="*70)
            print("Session complete!")
            print("="*70)
        
        return True

def main():
    tuner = LiveBeltTuner()
    tuner.run()

if __name__ == "__main__":
    main()
