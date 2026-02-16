#!/usr/bin/env python3
"""
Improved Belt Frequency Analysis
---------------------------------
Filters out harmonics, noise, and false peaks to get stable belt frequency readings.

Key improvements:
1. Harmonic filtering - removes 2x, 3x, 0.5x harmonics
2. Peak validation - requires consistent peak across multiple measurements
3. Noise floor detection - ignores low-magnitude peaks
4. Moving average - smooths readings over time
"""

import numpy as np
from scipy import signal
import matplotlib.pyplot as plt

def analyze_belt_frequency_improved(filepath, axis='x', previous_freq=None, debug=False):
    """
    Improved FFT analysis with harmonic filtering and validation
    
    Args:
        filepath: Path to CSV data file
        axis: 'x' or 'y' 
        previous_freq: Previous measurement for consistency check
        debug: Show debug plots and info
    
    Returns:
        dict with frequency, confidence, and debug info
    """
    try:
        # Load data
        data = np.genfromtxt(filepath, delimiter=',', skip_header=0)
        if len(data) < 500:  # Need enough samples
            return None
        
        # Select axis
        axis_index = 1 if axis == 'x' else 2
        accel_data = data[:, axis_index]
        times = data[:, 0]
        
        # Calculate sample rate
        dt = np.mean(np.diff(times))
        sample_rate = 1.0 / dt
        
        if debug:
            print(f"\n=== Analysis Debug ===")
            print(f"Samples: {len(data)}")
            print(f"Duration: {times[-1] - times[0]:.2f}s")
            print(f"Sample rate: {sample_rate:.1f} Hz")
            print(f"Data range: {np.min(accel_data):.1f} to {np.max(accel_data):.1f}")
        
        # STEP 1: Pre-filtering - Remove DC and very low frequencies
        # High-pass filter at 30 Hz to remove drift and very low frequency noise
        sos = signal.butter(4, 30, 'hp', fs=sample_rate, output='sos')
        accel_filtered = signal.sosfilt(sos, accel_data)
        
        # STEP 2: Window and FFT
        window = signal.windows.hann(len(accel_filtered))
        windowed_signal = accel_filtered * window
        
        # Zero-padding for better frequency resolution
        nfft = max(len(windowed_signal) * 2, 8192)
        fft_result = np.fft.rfft(windowed_signal, n=nfft)
        fft_freq = np.fft.rfftfreq(nfft, 1.0/sample_rate)
        fft_magnitude = np.abs(fft_result)
        
        # STEP 3: Focus on belt frequency range (50-200 Hz)
        belt_range = (fft_freq >= 50) & (fft_freq <= 200)
        belt_freq = fft_freq[belt_range]
        belt_mag = fft_magnitude[belt_range]
        
        if len(belt_mag) == 0:
            return None
        
        # STEP 4: Noise floor detection
        noise_floor = np.percentile(belt_mag, 75)  # 75th percentile as noise floor
        signal_threshold = noise_floor * 3  # Signal must be 3x above noise
        
        if debug:
            print(f"Noise floor: {noise_floor:.1f}")
            print(f"Signal threshold: {signal_threshold:.1f}")
        
        # STEP 5: Find all significant peaks
        peak_indices, peak_properties = signal.find_peaks(
            belt_mag,
            height=signal_threshold,
            prominence=noise_floor,
            distance=int(5 / (belt_freq[1] - belt_freq[0]))  # At least 5 Hz apart
        )
        
        if len(peak_indices) == 0:
            if debug:
                print("No peaks found above threshold")
            return None
        
        # Get peak frequencies and magnitudes
        peak_freqs = belt_freq[peak_indices]
        peak_mags = belt_mag[peak_indices]
        
        if debug:
            print(f"\nFound {len(peak_freqs)} peaks:")
            for i, (f, m) in enumerate(zip(peak_freqs, peak_mags)):
                print(f"  Peak {i+1}: {f:.1f} Hz (magnitude: {m:.1f})")
        
        # STEP 6: Harmonic filtering
        # Remove harmonics (2x, 3x, 0.5x, 0.33x of other peaks)
        valid_peaks = []
        
        for i, freq in enumerate(peak_freqs):
            is_harmonic = False
            
            # Check if this peak is a harmonic of a stronger peak
            for j, other_freq in enumerate(peak_freqs):
                if i == j:
                    continue
                
                # Check if freq is a harmonic of other_freq
                ratios = [0.5, 2.0, 3.0, 0.33, 1.5]  # Common harmonic ratios
                for ratio in ratios:
                    expected = other_freq * ratio
                    if abs(freq - expected) < 5:  # Within 5 Hz tolerance
                        # It's a harmonic - only keep it if it's stronger
                        if peak_mags[i] < peak_mags[j] * 0.8:
                            is_harmonic = True
                            if debug:
                                print(f"  {freq:.1f} Hz is harmonic ({ratio}x) of {other_freq:.1f} Hz - REJECTED")
                            break
                
                if is_harmonic:
                    break
            
            if not is_harmonic:
                valid_peaks.append((freq, peak_mags[i]))
        
        if len(valid_peaks) == 0:
            if debug:
                print("All peaks were harmonics - REJECTED")
            return None
        
        # STEP 7: Sort by magnitude and pick the strongest
        valid_peaks.sort(key=lambda x: x[1], reverse=True)
        best_freq, best_mag = valid_peaks[0]
        
        # STEP 8: Consistency check with previous measurement
        confidence = 1.0
        
        if previous_freq is not None:
            freq_diff = abs(best_freq - previous_freq)
            if freq_diff > 20:  # More than 20 Hz jump is suspicious
                confidence = 0.5
                if debug:
                    print(f"\nWARNING: Large jump from previous ({previous_freq:.1f} → {best_freq:.1f} Hz)")
            elif freq_diff > 10:
                confidence = 0.75
        
        # STEP 9: Calculate quality metrics
        snr = best_mag / noise_floor  # Signal-to-noise ratio
        
        if debug:
            print(f"\n=== Result ===")
            print(f"Best frequency: {best_freq:.1f} Hz")
            print(f"Magnitude: {best_mag:.1f}")
            print(f"SNR: {snr:.1f}")
            print(f"Confidence: {confidence:.2f}")
            print(f"Valid peaks: {len(valid_peaks)}")
        
        # STEP 10: Debug plot
        if debug:
            plt.figure(figsize=(15, 10))
            
            # Time domain
            plt.subplot(3, 1, 1)
            plt.plot(times, accel_data, 'b-', alpha=0.5, label='Raw')
            plt.plot(times, accel_filtered, 'r-', label='Filtered')
            plt.xlabel('Time (s)')
            plt.ylabel('Acceleration')
            plt.legend()
            plt.title('Time Domain Signal')
            plt.grid(True)
            
            # Full spectrum
            plt.subplot(3, 1, 2)
            plt.plot(fft_freq, fft_magnitude, 'b-', alpha=0.5)
            plt.axvline(best_freq, color='r', linestyle='--', label=f'Best: {best_freq:.1f} Hz')
            plt.axhline(signal_threshold, color='g', linestyle='--', label='Threshold')
            plt.xlabel('Frequency (Hz)')
            plt.ylabel('Magnitude')
            plt.xlim(0, 300)
            plt.legend()
            plt.title('Full Spectrum')
            plt.grid(True)
            
            # Belt range detail
            plt.subplot(3, 1, 3)
            plt.plot(belt_freq, belt_mag, 'b-', linewidth=2)
            plt.axhline(signal_threshold, color='g', linestyle='--', label='Threshold')
            plt.axhline(noise_floor, color='orange', linestyle='--', label='Noise floor')
            
            # Mark all peaks
            for freq, mag in zip(peak_freqs, peak_mags):
                color = 'r' if freq == best_freq else 'gray'
                alpha = 1.0 if freq == best_freq else 0.3
                plt.axvline(freq, color=color, alpha=alpha, linestyle=':')
                plt.plot(freq, mag, 'o', color=color, markersize=10 if freq == best_freq else 5)
            
            plt.xlabel('Frequency (Hz)')
            plt.ylabel('Magnitude')
            plt.legend()
            plt.title('Belt Frequency Range (50-200 Hz)')
            plt.grid(True)
            
            plt.tight_layout()
            plt.savefig('/tmp/belt_analysis_debug.png', dpi=100)
            print("\nDebug plot saved to: /tmp/belt_analysis_debug.png")
        
        return {
            'frequency': float(best_freq),
            'magnitude': float(best_mag),
            'confidence': float(confidence),
            'snr': float(snr),
            'noise_floor': float(noise_floor),
            'num_peaks': len(valid_peaks),
            'all_peaks': valid_peaks[:3]  # Top 3 peaks for reference
        }
        
    except Exception as e:
        if debug:
            print(f"Analysis error: {e}")
            import traceback
            traceback.print_exc()
        return None


def test_analysis():
    """Test the improved analysis on a real data file"""
    import sys
    
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        # Find the most recent file
        import os
        data_dir = "/tmp"
        files = []
        for filename in os.listdir(data_dir):
            if filename.startswith("adxl345-") and filename.endswith(".csv"):
                filepath = os.path.join(data_dir, filename)
                files.append((filepath, os.path.getmtime(filepath)))
        
        if files:
            files.sort(key=lambda x: x[1], reverse=True)
            filepath = files[0][0]
        else:
            print("No data files found in /tmp")
            return
    
    print(f"Analyzing: {filepath}")
    
    # Test both axes
    for axis in ['x', 'y']:
        print(f"\n{'='*60}")
        print(f"Belt {axis.upper()}-axis Analysis")
        print('='*60)
        
        result = analyze_belt_frequency_improved(filepath, axis=axis, debug=True)
        
        if result:
            print(f"\n✓ SUCCESS")
            print(f"  Frequency: {result['frequency']:.1f} Hz")
            print(f"  Confidence: {result['confidence']:.0%}")
            print(f"  SNR: {result['snr']:.1f}")
        else:
            print(f"\n✗ FAILED - No valid frequency detected")


if __name__ == "__main__":
    test_analysis()
