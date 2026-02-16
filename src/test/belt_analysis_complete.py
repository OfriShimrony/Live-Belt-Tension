#!/usr/bin/env python3
"""
Belt Tension Analyzer - Complete Signal Isolation Pipeline
-----------------------------------------------------------
Implements the full technical specification for isolating belt resonance
from structural noise using proper signal processing techniques.

Based on technical specification:
- DC offset removal
- Axis magnitude integration (orientation-agnostic)
- Hanning window (spectral leakage prevention)
- Band-pass filtering (60-250 Hz)
- SNR validation (3:1 minimum)
- Time-decay validation (STFT - proves it's mechanical resonance)
- Q-factor analysis (sharp peaks = belts, broad peaks = frame)
"""

import numpy as np
from scipy import signal as scipy_signal
from scipy.fft import rfft, rfftfreq
import matplotlib.pyplot as plt

def analyze_belt_with_full_pipeline(filepath, belt_name='Unknown', debug=False):
    """
    Complete signal processing pipeline for belt frequency detection
    
    Returns:
        dict with frequency, confidence, and diagnostic info
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
        
        print(f"\n{'='*70}")
        print(f"BELT TENSION ANALYSIS - {belt_name}")
        print(f"{'='*70}")
        print(f"Samples: {len(data)} @ {sample_rate:.0f} Hz")
        print(f"Duration: {times[-1] - times[0]:.2f}s")
        
        # ===================================================================
        # STEP 1: DC Offset Removal (Remove gravity component)
        # ===================================================================
        accel_x_centered = accel_x - np.mean(accel_x)
        accel_y_centered = accel_y - np.mean(accel_y)
        
        print(f"\n1. DC Offset Removed")
        print(f"   X: {np.mean(accel_x):.1f} → 0")
        print(f"   Y: {np.mean(accel_y):.1f} → 0")
        
        # ===================================================================
        # STEP 2: Axis Integration - Euclidean Magnitude (Orientation-Agnostic)
        # ===================================================================
        accel_magnitude = np.sqrt(accel_x_centered**2 + accel_y_centered**2)
        
        print(f"\n2. Axis Integration (Magnitude)")
        print(f"   Combined X & Y into orientation-agnostic signal")
        print(f"   Range: {np.min(accel_magnitude):.1f} to {np.max(accel_magnitude):.1f}")
        
        # ===================================================================
        # STEP 3: Temporal Windowing (Prevent spectral leakage)
        # ===================================================================
        window = np.hanning(len(accel_magnitude))
        windowed_signal = accel_magnitude * window
        
        print(f"\n3. Hanning Window Applied")
        print(f"   Prevents spectral leakage from finite sample")
        
        # ===================================================================
        # STEP 4: FFT Transform
        # ===================================================================
        fft_result = rfft(windowed_signal)
        fft_freq = rfftfreq(len(windowed_signal), 1.0/sample_rate)
        fft_mag = np.abs(fft_result)
        
        # ===================================================================
        # STEP 5: Band-pass Filter (60-250 Hz - physically plausible range)
        # ===================================================================
        belt_range = (fft_freq >= 60) & (fft_freq <= 250)
        belt_freq = fft_freq[belt_range]
        belt_mag = fft_mag[belt_range]
        
        print(f"\n4. Band-pass Filter (60-250 Hz)")
        print(f"   Removes floor vibrations (<60 Hz) and electrical noise (>250 Hz)")
        
        if len(belt_mag) == 0:
            return {'error': 'No data in belt frequency range'}
        
        # ===================================================================
        # STEP 6: Noise Floor & Peak Detection
        # ===================================================================
        noise_floor = np.percentile(belt_mag, 75)  # 75th percentile as noise
        threshold = noise_floor * 1.5
        
        peaks, properties = scipy_signal.find_peaks(
            belt_mag,
            height=threshold,
            prominence=noise_floor * 0.5,
            distance=int(5 / (belt_freq[1] - belt_freq[0]))
        )
        
        print(f"\n5. Peak Detection")
        print(f"   Noise floor: {noise_floor:.0f}")
        print(f"   Threshold: {threshold:.0f}")
        print(f"   Peaks found: {len(peaks)}")
        
        if len(peaks) == 0:
            return {'error': 'No peaks above noise floor'}
        
        peak_freqs = belt_freq[peaks]
        peak_mags = belt_mag[peaks]
        
        # Sort by magnitude
        sorted_indices = np.argsort(peak_mags)[::-1]
        
        # ===================================================================
        # STEP 7: Q-Factor Analysis (Peak Sharpness)
        # ===================================================================
        def calculate_q_factor(center_freq, center_mag, freqs, mags):
            """
            Calculate Q-factor (Quality factor) of a peak
            Q = center_frequency / bandwidth_at_half_power
            
            High Q (>10) = Sharp peak (belt resonance)
            Low Q (<5) = Broad peak (structural resonance)
            """
            half_power = center_mag / np.sqrt(2)
            
            # Find frequencies where magnitude is above half-power
            above_half = mags > half_power
            
            if np.sum(above_half) < 2:
                return 0  # Can't calculate bandwidth
            
            # Find bandwidth (frequency range where mag > half_power)
            half_power_indices = np.where(above_half)[0]
            bandwidth = freqs[half_power_indices[-1]] - freqs[half_power_indices[0]]
            
            if bandwidth == 0:
                return 0
            
            q_factor = center_freq / bandwidth
            return q_factor
        
        print(f"\n6. Q-Factor Analysis (Peak Sharpness)")
        print(f"   Rank  Frequency   SNR    Q-Factor  Type")
        print(f"   {'-'*50}")
        
        candidates = []
        
        for rank, i in enumerate(sorted_indices[:5], 1):
            freq = peak_freqs[i]
            mag = peak_mags[i]
            
            # Calculate SNR
            snr = mag / noise_floor
            
            # Calculate Q-factor
            q_factor = calculate_q_factor(freq, mag, belt_freq, belt_mag)
            
            # Classify peak
            if q_factor > 10 and snr > 3:
                peak_type = "✓ BELT (sharp, strong)"
            elif q_factor > 5:
                peak_type = "⚠ POSSIBLE (moderate)"
            else:
                peak_type = "✗ NOISE (broad/weak)"
            
            print(f"   {rank:2d}.  {freq:6.1f} Hz  {snr:5.1f}x  Q={q_factor:5.1f}  {peak_type}")
            
            candidates.append({
                'freq': freq,
                'mag': mag,
                'snr': snr,
                'q_factor': q_factor,
                'rank': rank
            })
        
        # ===================================================================
        # STEP 8: Time-Decay Validation (STFT)
        # ===================================================================
        print(f"\n7. Time-Decay Validation (STFT)")
        print(f"   Checking if peak decays over time (proof of resonance)...")
        
        # Split signal into 3 chunks
        chunk_size = len(accel_magnitude) // 3
        chunks = [
            accel_magnitude[0:chunk_size],
            accel_magnitude[chunk_size:2*chunk_size],
            accel_magnitude[2*chunk_size:3*chunk_size]
        ]
        
        # Analyze each chunk
        chunk_results = []
        for chunk_num, chunk in enumerate(chunks, 1):
            if len(chunk) < 100:
                continue
                
            # Window and FFT this chunk
            chunk_window = np.hanning(len(chunk))
            chunk_windowed = chunk * chunk_window
            chunk_fft = np.abs(rfft(chunk_windowed))
            chunk_freqs = rfftfreq(len(chunk_windowed), 1.0/sample_rate)
            
            # Find magnitude at candidate frequencies
            for candidate in candidates[:3]:  # Check top 3
                target_freq = candidate['freq']
                # Find closest frequency bin
                freq_idx = np.argmin(np.abs(chunk_freqs - target_freq))
                chunk_mag = chunk_fft[freq_idx]
                
                if 'decay_profile' not in candidate:
                    candidate['decay_profile'] = []
                candidate['decay_profile'].append(chunk_mag)
        
        # Check for decay pattern
        print(f"\n   Freq    Chunk1   Chunk2   Chunk3   Decay?")
        print(f"   {'-'*50}")
        
        for candidate in candidates[:3]:
            if 'decay_profile' in candidate and len(candidate['decay_profile']) == 3:
                profile = candidate['decay_profile']
                # Check if amplitude decreases over time
                is_decaying = profile[0] > profile[1] > profile[2]
                decay_str = "✓ YES" if is_decaying else "✗ NO"
                
                candidate['is_decaying'] = is_decaying
                
                print(f"   {candidate['freq']:5.1f}Hz  {profile[0]:7.0f}  {profile[1]:7.0f}  {profile[2]:7.0f}   {decay_str}")
        
        # ===================================================================
        # STEP 9: Select Best Candidate
        # ===================================================================
        print(f"\n{'='*70}")
        print(f"FINAL RESULT")
        print(f"{'='*70}")
        
        # Score candidates
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
        
        print(f"\nBest Candidate:")
        print(f"  Frequency: {best['freq']:.1f} Hz")
        print(f"  SNR: {best['snr']:.1f}:1")
        print(f"  Q-Factor: {best['q_factor']:.1f}")
        print(f"  Score: {best['score']}/10")
        
        if best['score'] >= 6:
            confidence = "HIGH"
            symbol = "✓"
        elif best['score'] >= 4:
            confidence = "MEDIUM"
            symbol = "⚠"
        else:
            confidence = "LOW"
            symbol = "✗"
        
        print(f"  Confidence: {symbol} {confidence}")
        print(f"{'='*70}")
        
        return {
            'frequency': best['freq'],
            'snr': best['snr'],
            'q_factor': best['q_factor'],
            'confidence': confidence,
            'score': best['score'],
            'all_candidates': candidates,
            'sample_rate': sample_rate,
            'samples': len(data)
        }
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 belt_analysis_complete.py <csv_file> [belt_name]")
        sys.exit(1)
    
    filepath = sys.argv[1]
    belt_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
    
    result = analyze_belt_with_full_pipeline(filepath, belt_name, debug=True)
    
    if 'error' not in result:
        print(f"\n✓ Analysis complete!")
        print(f"  Result: {result['frequency']:.1f} Hz ({result['confidence']} confidence)")
