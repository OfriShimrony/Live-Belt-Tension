#!/usr/bin/env python3
"""
Belt Frequency Analyzer - Event-Triggered Analysis
---------------------------------------------------
Implements proper signal processing based on technical specification:

1. Event detection (finds the pluck moment)
2. Windowed analysis (only analyzes 1s after pluck)
3. Parabolic interpolation (sub-Hz accuracy)
4. High Q-factor validation
5. Band-pass filtering (80-160 Hz belt range only)

This ignores "dead air" and focuses on the resonance event.
"""

import numpy as np
from scipy import signal as scipy_signal
from scipy.fft import rfft, rfftfreq
from scipy.interpolate import interp1d

def find_pluck_trigger(accel_magnitude, sample_rate, threshold_multiplier=3.0):
    """
    Find the moment of the pluck by detecting sudden variance spike.
    
    Uses sliding window variance to find when acceleration spikes suddenly.
    This is "Timestamp Zero" of the pluck event.
    
    Args:
        accel_magnitude: Combined acceleration magnitude vector
        sample_rate: Sample rate in Hz
        threshold_multiplier: How many std devs above mean to trigger
    
    Returns:
        Index of pluck trigger point (or None if not found)
    """
    # Window size: 50ms
    window_samples = int(0.05 * sample_rate)
    
    # Calculate rolling variance
    variances = []
    for i in range(len(accel_magnitude) - window_samples):
        window = accel_magnitude[i:i+window_samples]
        variances.append(np.var(window))
    
    variances = np.array(variances)
    
    # Find where variance spikes above threshold
    mean_var = np.mean(variances)
    std_var = np.std(variances)
    threshold = mean_var + (threshold_multiplier * std_var)
    
    # Find first spike
    spikes = np.where(variances > threshold)[0]
    
    if len(spikes) > 0:
        return spikes[0]
    
    return None

def parabolic_interpolation(fft_freq, fft_mag, peak_index):
    """
    Use parabolic interpolation for sub-Hz accuracy.
    
    Looks at neighbor bins of the peak to find true center.
    Allows distinguishing 115.1 Hz from 115.4 Hz.
    
    Args:
        fft_freq: Frequency array
        fft_mag: Magnitude array
        peak_index: Index of peak bin
    
    Returns:
        Interpolated frequency with sub-Hz precision
    """
    if peak_index <= 0 or peak_index >= len(fft_mag) - 1:
        return fft_freq[peak_index]
    
    # Get three points around peak
    y1 = fft_mag[peak_index - 1]
    y2 = fft_mag[peak_index]
    y3 = fft_mag[peak_index + 1]
    
    # Parabolic interpolation formula
    delta = 0.5 * (y1 - y3) / (y1 - 2*y2 + y3)
    
    # Interpolated frequency
    freq_resolution = fft_freq[1] - fft_freq[0]
    interpolated_freq = fft_freq[peak_index] + delta * freq_resolution
    
    return interpolated_freq

def calculate_q_factor_bandwidth(freq, mag, freqs, mags):
    """
    Calculate Q-factor by measuring peak bandwidth at half-power.
    
    Q = center_frequency / bandwidth
    High Q (>80) = sharp pure vibration
    Low Q (<10) = broad noisy peak
    """
    half_power = mag / np.sqrt(2)
    
    # Find frequencies where magnitude > half_power
    above_half = mags > half_power
    
    if np.sum(above_half) < 2:
        return 0
    
    indices = np.where(above_half)[0]
    bandwidth = freqs[indices[-1]] - freqs[indices[0]]
    
    if bandwidth == 0:
        return 0
    
    return freq / bandwidth

def analyze_pluck_event(filepath, belt_name='Unknown', debug=False):
    """
    Analyze belt pluck with event-triggered processing.
    
    Returns dict with:
        - frequency: Detected frequency with sub-Hz accuracy
        - confidence: Based on Q-factor and peak sharpness
        - q_factor: Peak sharpness (>80 = excellent)
        - trigger_time: When pluck was detected
    """
    
    try:
        # ===================================================================
        # STEP 1: Load and prepare data
        # ===================================================================
        data = np.genfromtxt(filepath, delimiter=',', skip_header=1)
        if len(data) < 1000:
            return {'error': 'Insufficient samples', 'samples': len(data)}
        
        times = data[:, 0]
        accel_x = data[:, 1]
        accel_y = data[:, 2]
        
        dt = np.mean(np.diff(times))
        sample_rate = 1.0 / dt
        
        if debug:
            print(f"Sample rate: {sample_rate:.0f} Hz")
            print(f"Duration: {times[-1] - times[0]:.2f}s")
        
        # ===================================================================
        # STEP 2: Axis merging - Magnitude extraction
        # ===================================================================
        accel_x_centered = accel_x - np.mean(accel_x)
        accel_y_centered = accel_y - np.mean(accel_y)
        accel_magnitude = np.sqrt(accel_x_centered**2 + accel_y_centered**2)
        
        if debug:
            print(f"Max magnitude: {np.max(accel_magnitude):.0f}")
        
        # ===================================================================
        # STEP 3: Event detection - Find the pluck moment
        # ===================================================================
        trigger_idx = find_pluck_trigger(accel_magnitude, sample_rate)
        
        if trigger_idx is None:
            return {'error': 'No pluck event detected'}
        
        trigger_time = times[trigger_idx]
        
        if debug:
            print(f"Pluck detected at t={trigger_time:.3f}s (sample {trigger_idx})")
        
        # ===================================================================
        # STEP 4: Extract 1-second window after trigger
        # ===================================================================
        # Start 20ms after trigger (to skip the initial "clunk")
        start_offset = int(0.02 * sample_rate)
        start_idx = trigger_idx + start_offset
        
        # Window length: 1 second (or less if not enough data)
        window_samples = min(int(1.0 * sample_rate), len(accel_magnitude) - start_idx)
        
        if window_samples < 512:
            return {'error': 'Insufficient data after trigger'}
        
        signal_window = accel_magnitude[start_idx:start_idx + window_samples]
        
        if debug:
            print(f"Analysis window: {len(signal_window)} samples ({len(signal_window)/sample_rate:.3f}s)")
        
        # ===================================================================
        # STEP 5: Windowing and FFT
        # ===================================================================
        hanning_window = np.hanning(len(signal_window))
        windowed_signal = signal_window * hanning_window
        
        fft_result = rfft(windowed_signal)
        fft_freq = rfftfreq(len(windowed_signal), 1.0/sample_rate)
        fft_mag = np.abs(fft_result)
        
        # ===================================================================
        # STEP 6: Band-pass filter (80-160 Hz belt range)
        # ===================================================================
        # This automatically ignores 176 Hz structural noise
        belt_range = (fft_freq >= 80) & (fft_freq <= 160)
        belt_freq = fft_freq[belt_range]
        belt_mag = fft_mag[belt_range]
        
        if len(belt_mag) == 0:
            return {'error': 'No data in belt frequency range'}
        
        if debug:
            print(f"Belt range (80-160 Hz): {len(belt_freq)} bins")
        
        # ===================================================================
        # STEP 7: Find highest peak
        # ===================================================================
        peak_idx = np.argmax(belt_mag)
        peak_freq_raw = belt_freq[peak_idx]
        peak_mag = belt_mag[peak_idx]
        
        # ===================================================================
        # STEP 8: Parabolic interpolation for sub-Hz accuracy
        # ===================================================================
        # Map back to original indices for interpolation
        original_peak_idx = np.where(fft_freq == peak_freq_raw)[0][0]
        peak_freq_refined = parabolic_interpolation(fft_freq, fft_mag, original_peak_idx)
        
        if debug:
            print(f"Raw peak: {peak_freq_raw:.1f} Hz")
            print(f"Refined peak: {peak_freq_refined:.2f} Hz")
        
        # ===================================================================
        # STEP 9: Calculate Q-factor (sharpness)
        # ===================================================================
        q_factor = calculate_q_factor_bandwidth(peak_freq_refined, peak_mag, belt_freq, belt_mag)
        
        if debug:
            print(f"Q-factor: {q_factor:.1f}")
        
        # ===================================================================
        # STEP 10: Confidence scoring
        # ===================================================================
        confidence_score = 0
        
        # Q-factor based confidence
        if q_factor > 80:
            confidence = "EXCELLENT"
            confidence_score = 10
        elif q_factor > 50:
            confidence = "HIGH"
            confidence_score = 8
        elif q_factor > 20:
            confidence = "GOOD"
            confidence_score = 6
        elif q_factor > 10:
            confidence = "MEDIUM"
            confidence_score = 4
        else:
            confidence = "LOW"
            confidence_score = 2
        
        # Check if in expected belt range (90-130 Hz typical)
        if 90 <= peak_freq_refined <= 130:
            confidence_score += 2
        
        return {
            'frequency': float(peak_freq_refined),
            'confidence': confidence,
            'confidence_score': confidence_score,
            'q_factor': float(q_factor),
            'trigger_time': float(trigger_time),
            'trigger_index': int(trigger_idx),
            'peak_magnitude': float(peak_mag),
            'sample_rate': float(sample_rate),
            'analysis_window_duration': float(len(signal_window) / sample_rate)
        }
        
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}

def main():
    """Test the analyzer on calibration files"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 belt_analyzer_v2.py <csv_file>")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    print("="*70)
    print("BELT FREQUENCY ANALYZER V2")
    print("Event-Triggered Analysis with Parabolic Interpolation")
    print("="*70)
    print()
    
    result = analyze_pluck_event(filepath, debug=True)
    
    print()
    print("="*70)
    print("RESULT")
    print("="*70)
    
    if 'error' in result:
        print(f"✗ Error: {result['error']}")
        if 'traceback' in result:
            print()
            print(result['traceback'])
    else:
        print(f"Frequency: {result['frequency']:.2f} Hz")
        print(f"Confidence: {result['confidence']} ({result['confidence_score']}/12)")
        print(f"Q-Factor: {result['q_factor']:.1f}")
        print(f"Trigger: t={result['trigger_time']:.3f}s")
    
    print("="*70)

if __name__ == "__main__":
    main()
