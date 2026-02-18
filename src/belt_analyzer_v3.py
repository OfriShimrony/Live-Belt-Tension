#!/usr/bin/env python3
"""
Belt Frequency Analyzer V3
---------------------------
Improvements over V2:

1. Max-Peak Triggering (replaces rolling variance)
   - Finds absolute maximum acceleration (the "snap")
   - Starts analysis 50ms after peak (skips impact noise)
   - Consistent window regardless of pluck sharpness

2. Zero-Padding (4x)
   - Pads FFT to next power of 2 * 4
   - Smoother curve for parabolic interpolation
   - Better sub-Hz accuracy

3. Welch's PSD Method
   - Averages multiple overlapping windows
   - Reduces noise for weak signals (Belt B problem)
   - More reliable frequency detection

4. Tighter Band-pass (90-140 Hz)
   - Completely excludes 176Hz structural resonance
   - Isolates belt operating range only

5. Notch filter at 176Hz
   - Explicitly removes structural ghost frequency
"""

import numpy as np
from scipy import signal as scipy_signal
from scipy.fft import rfft, rfftfreq


def find_peak_trigger(accel_magnitude, sample_rate):
    """
    Max-Peak Triggering - finds absolute maximum acceleration.
    The physical moment of the snap.
    Analysis starts 50ms after this peak to skip impact noise.
    Much more robust than rolling variance.
    """
    peak_idx = int(np.argmax(np.abs(accel_magnitude)))
    return peak_idx


def apply_notch_filter(signal_data, sample_rate, notch_freq=176.0, quality=30.0):
    """Notch filter to remove structural resonance at 176Hz"""
    b, a = scipy_signal.iirnotch(notch_freq, quality, sample_rate)
    return scipy_signal.filtfilt(b, a, signal_data)


def apply_bandpass_filter(signal_data, sample_rate, low=90.0, high=140.0):
    """
    Tight band-pass filter (90-140 Hz).
    Completely excludes 176Hz structural resonance.
    Isolates belt operating range only.
    """
    nyq = sample_rate / 2.0
    b, a = scipy_signal.butter(4, [low / nyq, high / nyq], btype='band')
    return scipy_signal.filtfilt(b, a, signal_data)


def calculate_psd_welch(signal_data, sample_rate):
    """
    Welch's Power Spectral Density.
    Averages overlapping windows to reduce noise.
    Much better for weak/noisy signals like Belt B.
    """
    nperseg = min(len(signal_data), int(sample_rate * 0.25))
    noverlap = nperseg // 2

    freqs, psd = scipy_signal.welch(
        signal_data,
        fs=sample_rate,
        nperseg=nperseg,
        noverlap=noverlap,
        window='hann'
    )
    return freqs, psd


def calculate_fft_zero_padded(signal_data, sample_rate):
    """
    Zero-padded FFT (4x padding).
    Creates smoother spectrum for parabolic interpolation.
    """
    n_fft = 2 ** int(np.ceil(np.log2(len(signal_data))) + 2)
    window = np.hanning(len(signal_data))
    windowed = signal_data * window
    spectrum = np.abs(rfft(windowed, n=n_fft))
    freqs = rfftfreq(n_fft, 1.0 / sample_rate)
    return freqs, spectrum


def parabolic_interpolation(freqs, magnitudes, peak_idx):
    """Sub-Hz accuracy via parabolic interpolation"""
    if peak_idx <= 0 or peak_idx >= len(magnitudes) - 1:
        return freqs[peak_idx]

    y1 = magnitudes[peak_idx - 1]
    y2 = magnitudes[peak_idx]
    y3 = magnitudes[peak_idx + 1]

    denom = y1 - 2 * y2 + y3
    if denom == 0:
        return freqs[peak_idx]

    delta = 0.5 * (y1 - y3) / denom
    freq_resolution = freqs[1] - freqs[0]
    return freqs[peak_idx] + delta * freq_resolution


def calculate_q_factor(freq, freqs, magnitudes):
    """Calculate Q-factor (peak sharpness)"""
    peak_idx = np.argmin(np.abs(freqs - freq))
    peak_mag = magnitudes[peak_idx]
    half_power = peak_mag / np.sqrt(2)

    above_half = magnitudes > half_power
    if np.sum(above_half) < 2:
        return 0

    indices = np.where(above_half)[0]
    bandwidth = freqs[indices[-1]] - freqs[indices[0]]

    if bandwidth == 0:
        return 0

    return freq / bandwidth


def analyze_pluck_event(filepath, belt_name='Unknown', debug=False):
    """
    V3 Analysis Pipeline:
    1. Load data
    2. Magnitude extraction (X+Y, DC removed)
    3. Max-peak triggering (robust to pluck sharpness)
    4. Extract window: 50ms after peak, 1s duration
    5. Notch filter at 176Hz (structural ghost)
    6. Tight band-pass (90-140 Hz)
    7. Welch PSD (noise reduction, initial estimate)
    8. Zero-padded FFT (smooth spectrum)
    9. Peak detection near PSD estimate
    10. Parabolic interpolation (sub-Hz precision)
    11. Q-factor and confidence
    """
    try:
        # STEP 1: Load data
        data = np.genfromtxt(filepath, delimiter=',', skip_header=1)
        if len(data) < 1000:
            return {'error': 'Insufficient samples'}

        times = data[:, 0]
        accel_x = data[:, 1]
        accel_y = data[:, 2]

        dt = np.mean(np.diff(times))
        sample_rate = 1.0 / dt

        if debug:
            print(f"Samples: {len(data)}, Rate: {sample_rate:.0f}Hz, "
                  f"Duration: {times[-1]-times[0]:.2f}s")

        # STEP 2: Magnitude (DC removed)
        accel_x -= np.mean(accel_x)
        accel_y -= np.mean(accel_y)
        accel_magnitude = np.sqrt(accel_x**2 + accel_y**2)

        # STEP 3: Max-peak trigger
        peak_idx = find_peak_trigger(accel_magnitude, sample_rate)
        trigger_time = times[peak_idx]

        if debug:
            print(f"Peak at t={trigger_time:.3f}s (idx={peak_idx}), "
                  f"mag={accel_magnitude[peak_idx]:.0f}")

        # STEP 4: Window - 50ms after peak, 1s duration
        skip_samples = int(0.05 * sample_rate)
        start_idx = peak_idx + skip_samples
        end_idx = min(start_idx + int(1.0 * sample_rate), len(accel_magnitude))

        if (end_idx - start_idx) < 512:
            return {'error': 'Insufficient data after trigger'}

        signal_window = accel_magnitude[start_idx:end_idx]

        if debug:
            print(f"Window: {len(signal_window)} samples "
                  f"({len(signal_window)/sample_rate:.3f}s)")

        # STEP 5: Notch filter 176Hz
        signal_notched = apply_notch_filter(signal_window, sample_rate)

        # STEP 6: Band-pass 90-140Hz
        signal_filtered = apply_bandpass_filter(signal_notched, sample_rate)

        # STEP 7: Welch PSD for initial estimate
        psd_freqs, psd_power = calculate_psd_welch(signal_filtered, sample_rate)
        belt_mask = (psd_freqs >= 90) & (psd_freqs <= 140)
        belt_psd_freqs = psd_freqs[belt_mask]
        belt_psd_power = psd_power[belt_mask]

        if len(belt_psd_freqs) == 0:
            return {'error': 'No PSD data in belt range'}

        psd_peak_freq = belt_psd_freqs[np.argmax(belt_psd_power)]

        if debug:
            print(f"PSD estimate: {psd_peak_freq:.1f}Hz")

        # STEP 8: Zero-padded FFT
        fft_freqs, fft_spectrum = calculate_fft_zero_padded(signal_filtered, sample_rate)

        belt_fft_mask = (fft_freqs >= 90) & (fft_freqs <= 140)
        belt_fft_freqs = fft_freqs[belt_fft_mask]
        belt_fft_spectrum = fft_spectrum[belt_fft_mask]

        if len(belt_fft_freqs) == 0:
            return {'error': 'No FFT data in belt range'}

        # STEP 9: Peak near PSD estimate
        search_mask = (belt_fft_freqs >= psd_peak_freq - 5) & \
                      (belt_fft_freqs <= psd_peak_freq + 5)

        if np.sum(search_mask) > 0:
            local_peak_idx = np.argmax(belt_fft_spectrum[search_mask])
            global_peak_idx = np.where(belt_fft_mask)[0][
                np.where(search_mask)[0][local_peak_idx]
            ]
        else:
            global_peak_idx = np.where(belt_fft_mask)[0][
                np.argmax(belt_fft_spectrum)
            ]

        # STEP 10: Parabolic interpolation
        final_freq = parabolic_interpolation(fft_freqs, fft_spectrum, global_peak_idx)

        if debug:
            print(f"FFT peak: {fft_freqs[global_peak_idx]:.2f}Hz → "
                  f"Interpolated: {final_freq:.3f}Hz")

        # STEP 11: Q-factor and confidence
        q_factor = calculate_q_factor(final_freq, belt_fft_freqs, belt_fft_spectrum)

        if q_factor > 50:
            confidence = "EXCELLENT"
        elif q_factor > 20:
            confidence = "HIGH"
        elif q_factor > 10:
            confidence = "GOOD"
        else:
            confidence = "LOW"

        return {
            'frequency': float(final_freq),
            'q_factor': float(q_factor),
            'confidence': confidence,
            'trigger_time': float(trigger_time),
            'psd_estimate': float(psd_peak_freq),
            'sample_rate': float(sample_rate),
        }

    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}


# Alias for belt_tuner_panel.py import compatibility
analyze_pluck_v3 = analyze_pluck_event


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 belt_analyzer_v3.py <csv_file>")
        sys.exit(1)

    result = analyze_pluck_event(sys.argv[1], debug=True)
    print()
    print("=" * 50)
    if 'error' in result:
        print(f"ERROR: {result['error']}")
        if 'traceback' in result:
            print(result['traceback'])
    else:
        print(f"Frequency:  {result['frequency']:.3f} Hz")
        print(f"PSD Est:    {result['psd_estimate']:.1f} Hz")
        print(f"Q-Factor:   {result['q_factor']:.1f}")
        print(f"Confidence: {result['confidence']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
