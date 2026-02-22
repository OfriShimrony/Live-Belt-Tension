#!/usr/bin/env python3
"""
Belt Sweep Analyzer — for motion-based belt frequency measurement.

Analyzes raw accelerometer CSV from Klipper's TEST_RESONANCES (OUTPUT=raw_data).
Unlike V3 (pluck/ring-down), this operates on the full frequency-sweep dataset.

Main entry point: analyze_sweep_csv(filepath, belt_name, freq_min, freq_max)
Returns the same dict shape as belt_analyzer_v3 for compatibility.
"""

import numpy as np
from scipy import signal
import os


def analyze_sweep_csv(filepath, belt_name='?', freq_min=85.0, freq_max=140.0, debug=False):
    """
    Analyze a raw resonance CSV (from TEST_RESONANCES OUTPUT=raw_data) to find
    the belt resonant frequency.

    Args:
        filepath:  Path to the CSV file.
        belt_name: Label for logging (e.g. 'A' or 'B').
        freq_min:  Lower bound of belt frequency search range (Hz).
        freq_max:  Upper bound of belt frequency search range (Hz).
        debug:     Print extra diagnostics if True.

    Returns dict with keys:
        frequency   – float Hz, or None on error
        confidence  – 'HIGH' / 'MEDIUM' / 'LOW' / 'UNRELIABLE'
        q_factor    – SNR (used as quality proxy, compatible with V3 output)
        snr         – same value under its proper name
        sample_rate – float Hz
        error       – None on success, string on failure
    """

    FAIL = lambda msg: {
        'frequency': None, 'confidence': None, 'q_factor': None,
        'snr': None, 'sample_rate': None, 'error': msg
    }

    # ── 1. Load CSV ────────────────────────────────────────────────────────────
    times, ax, ay = [], [], []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) < 3:
                    continue
                try:
                    times.append(float(parts[0]))
                    ax.append(float(parts[1]))
                    ay.append(float(parts[2]))
                except ValueError:
                    continue
    except Exception as e:
        return FAIL(f'Read error: {e}')

    if len(times) < 500:
        return FAIL(f'Insufficient data ({len(times)} samples)')

    times = np.array(times)
    ax    = np.array(ax)
    ay    = np.array(ay)

    # ── 2. Sample rate ─────────────────────────────────────────────────────────
    diffs = np.diff(times)
    fs = 1.0 / np.median(diffs)
    if debug:
        print(f'[sweep] fs={fs:.1f} Hz  samples={len(times)}  '
              f'duration={times[-1]-times[0]:.1f}s')

    # ── 3. 2-D magnitude (motion is in XY plane for diagonal axis) ─────────────
    mag = np.sqrt(ax**2 + ay**2)
    mag -= np.mean(mag)   # DC removal

    # ── 4. Welch PSD on full dataset ───────────────────────────────────────────
    # Use ~2-second segments for frequency resolution; never more than len/4
    nperseg = min(int(fs * 2.0), len(mag) // 4)
    nperseg = max(nperseg, 256)

    freqs, psd = signal.welch(
        mag, fs,
        nperseg=nperseg,
        noverlap=nperseg // 2,
        window='hann'
    )

    # ── 5. Search target range ─────────────────────────────────────────────────
    mask = (freqs >= freq_min) & (freqs <= freq_max)
    if not np.any(mask):
        return FAIL(f'No frequency bins in {freq_min}–{freq_max} Hz')

    psd_r  = psd[mask]
    freq_r = freqs[mask]

    peak_idx   = int(np.argmax(psd_r))
    peak_freq  = float(freq_r[peak_idx])
    peak_power = float(psd_r[peak_idx])

    # ── 6. Parabolic interpolation for sub-bin precision ──────────────────────
    if 0 < peak_idx < len(psd_r) - 1:
        y0, y1, y2 = psd_r[peak_idx-1], psd_r[peak_idx], psd_r[peak_idx+1]
        denom = 2 * (2*y1 - y0 - y2)
        if denom != 0:
            delta     = (y2 - y0) / denom
            freq_step = float(freq_r[1] - freq_r[0]) if len(freq_r) > 1 else 0.0
            peak_freq = float(peak_freq + delta * freq_step)

    peak_freq = round(peak_freq, 1)

    # ── 7. Noise floor & SNR ──────────────────────────────────────────────────
    noise_floor = float(np.median(psd_r))
    noise_floor = max(noise_floor, 1e-12)
    snr = peak_power / noise_floor

    if snr > 15:
        confidence = 'HIGH'
    elif snr > 7:
        confidence = 'MEDIUM'
    elif snr > 3:
        confidence = 'LOW'
    else:
        confidence = 'UNRELIABLE'

    if debug:
        print(f'[sweep] Belt {belt_name}: {peak_freq} Hz  SNR={snr:.1f}  {confidence}')

    return {
        'frequency':   peak_freq,
        'confidence':  confidence,
        'q_factor':    round(snr, 1),   # SNR used as quality proxy
        'snr':         round(snr, 1),
        'sample_rate': round(fs, 1),
        'error':       None,
    }


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: belt_sweep_analyzer.py <csv_file> [freq_min] [freq_max]')
        sys.exit(1)
    fmin = float(sys.argv[2]) if len(sys.argv) > 2 else 85.0
    fmax = float(sys.argv[3]) if len(sys.argv) > 3 else 140.0
    result = analyze_sweep_csv(sys.argv[1], freq_min=fmin, freq_max=fmax, debug=True)
    if result['error']:
        print(f'Error: {result["error"]}')
    else:
        print(f'Frequency: {result["frequency"]} Hz')
        print(f'Confidence: {result["confidence"]}  SNR: {result["snr"]}')
