#!/usr/bin/env python3
"""
Belt Sweep Analyzer — for motion-based belt frequency measurement.

Analyzes raw accelerometer CSV from Klipper's TEST_RESONANCES (OUTPUT=raw_data).
Unlike V3 (pluck/ring-down), this operates on the full frequency-sweep dataset.

Main entry points:
  analyze_sweep_csv(filepath, belt_name, freq_min, freq_max)
      Single-position sweep analysis.  Returns same dict shape as belt_analyzer_v3.

  analyze_multi_position_sweep(scans, belt_name, axis, ...)
      Multi-position analysis: runs scans at Y=80, 100, 120, then discriminates
      belt resonances (shift with Y) from structural resonances (fixed with Y).
"""

import numpy as np
from scipy import signal
import os


# ══════════════════════════════════════════════════════════════════════════════
# Private helpers
# ══════════════════════════════════════════════════════════════════════════════

def _load_and_project(filepath, axis=''):
    """
    Load a raw resonance CSV and return (times, mag, fs).

    mag is either the axis-projected signal (if axis is parseable) or the
    2-D magnitude sqrt(ax^2 + ay^2).  DC is removed from mag.

    Returns (None, None, None) on any error (file missing, too short, etc.).
    """
    times_l, ax_l, ay_l = [], [], []
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
                    times_l.append(float(parts[0]))
                    ax_l.append(float(parts[1]))
                    ay_l.append(float(parts[2]))
                except ValueError:
                    continue
    except Exception:
        return None, None, None

    if len(times_l) < 500:
        return None, None, None

    times = np.array(times_l)
    ax    = np.array(ax_l)
    ay    = np.array(ay_l)
    fs    = 1.0 / float(np.median(np.diff(times)))

    # Axis projection
    proj = None
    if axis:
        try:
            parts_ax = [float(v) for v in axis.replace(' ', '').split(',')]
            if len(parts_ax) >= 2:
                nx, ny = parts_ax[0], parts_ax[1]
                norm = np.sqrt(nx**2 + ny**2)
                if norm > 0:
                    proj = (ax * nx + ay * ny) / norm
        except (ValueError, ZeroDivisionError):
            proj = None

    mag = proj if proj is not None else np.sqrt(ax**2 + ay**2)
    mag = mag - np.mean(mag)   # DC removal
    return times, mag, fs


def _extract_peaks(filepath, axis='', freq_min=85.0, freq_max=140.0, n=10):
    """
    Return the top-N (freq_hz, norm_power) peaks from one scan CSV.

    norm_power is normalised so the highest peak in the band = 1.0.
    Peaks are found in the zero-padded FFT of the full signal.

    Returns empty list on any error.
    """
    times, mag, fs = _load_and_project(filepath, axis)
    if mag is None:
        return []

    n_fft = 1
    while n_fft < len(mag) * 8:
        n_fft <<= 1

    win  = np.hanning(len(mag))
    spec = np.abs(np.fft.rfft(mag * win, n=n_fft)) ** 2
    freqs = np.fft.rfftfreq(n_fft, 1.0 / fs)

    mask   = (freqs >= freq_min) & (freqs <= freq_max)
    psd_r  = spec[mask]
    freq_r = freqs[mask]

    if not np.any(mask) or np.max(psd_r) == 0:
        return []

    psd_norm = psd_r / np.max(psd_r)

    # Minimum separation ~3 Hz between peaks
    bin_hz    = float(freq_r[1] - freq_r[0]) if len(freq_r) > 1 else 1.0
    min_dist  = max(1, int(3.0 / bin_hz))
    peak_idxs, _ = signal.find_peaks(psd_norm, distance=min_dist)

    if len(peak_idxs) == 0:
        return []

    # Parabolic interpolation for sub-bin precision
    results = []
    for idx in peak_idxs:
        f = float(freq_r[idx])
        p = float(psd_norm[idx])
        if 0 < idx < len(psd_r) - 1:
            y0, y1, y2 = psd_r[idx-1], psd_r[idx], psd_r[idx+1]
            denom = 2 * (2*y1 - y0 - y2)
            if denom != 0:
                delta = (y2 - y0) / denom
                f = float(f + delta * bin_hz)
        results.append((round(f, 2), round(p, 4)))

    # Sort by power descending, return top N
    results.sort(key=lambda x: -x[1])
    return results[:n]


def _interpolate_calibration(calibration, y_pos):
    """
    Linearly interpolate the expected belt frequency at y_pos from calibration.

    calibration: list of {'y': float, 'freq': float}, sorted ascending by y.
    Returns float Hz, or None if calibration is empty.
    """
    if not calibration:
        return None
    ys    = np.array([c['y']    for c in calibration], dtype=float)
    freqs = np.array([c['freq'] for c in calibration], dtype=float)
    return float(np.interp(y_pos, ys, freqs))


def _interpolate_freq_at_y(freqs_by_y, target_y):
    """
    Linearly interpolate a belt frequency at target_y from a {y: freq} dict.

    Returns float Hz, or None if fewer than 2 data points.
    """
    if len(freqs_by_y) < 2:
        return None
    ys    = sorted(freqs_by_y.keys())
    fvals = [freqs_by_y[y] for y in ys]
    return float(np.interp(target_y, ys, fvals))


def _fallback_single_position(per_position, belt_name):
    """
    When multi-position discrimination fails, return the single-position result
    closest to Y=100 (or the only position if just one was scanned).
    """
    # Prefer Y=100 exactly, then closest
    best = min(per_position, key=lambda p: abs(p['y_pos'] - 100.0))
    r = dict(best['single'])
    r['method']           = 'multi_position'
    r['position_results'] = [
        {'y_pos': p['y_pos'], 'frequency': p['single']['frequency'],
         'confidence': p['single']['confidence'], 'snr': p['single']['snr']}
        for p in per_position
    ]
    r['peak_mobility']  = 0.0
    r['classification'] = 'structural_only'
    return r


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def analyze_sweep_csv(filepath, belt_name='?', freq_min=85.0, freq_max=140.0,
                      axis='', debug=False):
    """
    Analyze a raw resonance CSV (from TEST_RESONANCES OUTPUT=raw_data) to find
    the belt resonant frequency.

    Args:
        filepath:  Path to the CSV file.
        belt_name: Label for logging (e.g. 'A' or 'B').
        freq_min:  Lower bound of belt frequency search range (Hz).
        freq_max:  Upper bound of belt frequency search range (Hz).
        axis:      Scan axis string e.g. '1,1' or '1,-1'. When provided the
                   accelerometer signal is projected onto this axis before
                   analysis, isolating the relevant belt.  Also enables the
                   time-frequency matched peak selection (see below).
                   Falls back to 2-D magnitude if empty or unparseable.
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
    times, mag, fs = _load_and_project(filepath, axis)
    if times is None:
        # Determine specific error
        try:
            with open(filepath, 'r') as f:
                lines = [l for l in f if not l.startswith('#') and l.strip()]
            if len(lines) < 500:
                return FAIL(f'Insufficient data ({len(lines)} samples)')
        except Exception as e:
            return FAIL(f'Read error: {e}')
        return FAIL('Failed to load CSV')

    proj_used = axis and mag is not None  # True if axis projection was applied

    if debug:
        print(f'[sweep] fs={fs:.1f} Hz  samples={len(times)}  '
              f'duration={times[-1]-times[0]:.1f}s')
        if proj_used:
            print(f'[sweep] Using axis projection ({axis})')
        else:
            print('[sweep] Using 2-D magnitude (no axis)')

    # ── 2. Zero-padded FFT for high-resolution spectrum ───────────────────────
    n_fft = 1
    while n_fft < len(mag) * 8:
        n_fft <<= 1

    win  = np.hanning(len(mag))
    spec = np.abs(np.fft.rfft(mag * win, n=n_fft)) ** 2
    freqs = np.fft.rfftfreq(n_fft, 1.0 / fs)

    # ── 3. Search target range ─────────────────────────────────────────────────
    mask = (freqs >= freq_min) & (freqs <= freq_max)
    if not np.any(mask):
        return FAIL(f'No frequency bins in {freq_min}-{freq_max} Hz')

    psd_r  = spec[mask]
    freq_r = freqs[mask]

    # ── 4. Time-frequency matched peak selection (axis projection only) ────────
    # Structural resonances are continuously excited throughout the sweep and
    # therefore dominate the full-signal FFT.  Belt resonances are excited only
    # when the sweep drives them, producing a brief ring-down.
    #
    # Strategy: build a spectrogram, then score each candidate frequency by how
    # much its power peaks at the *expected* sweep time vs. the baseline power
    # at all other times.  A true belt resonance scores high (peak >> baseline);
    # a persistent structural resonance scores low (peak ≈ baseline).
    #
    # The spectrogram gives an approximate frequency (±3-5 Hz); the zero-padded
    # FFT above is then searched in a narrow window around that estimate for
    # sub-Hz precision.
    peak_idx = int(np.argmax(psd_r))   # default: raw FFT max

    # Determine if axis projection was actually used (re-check signal vs 2D mag)
    _axis_proj_active = False
    if axis:
        try:
            parts_ax = [float(v) for v in axis.replace(' ', '').split(',')]
            if len(parts_ax) >= 2:
                nx, ny = parts_ax[0], parts_ax[1]
                if np.sqrt(nx**2 + ny**2) > 0:
                    _axis_proj_active = True
        except (ValueError, ZeroDivisionError):
            pass

    if _axis_proj_active:
        duration_actual = float(times[-1] - times[0])
        if duration_actual > 5.0 and (freq_max - freq_min) > 10.0:
            sweep_rate = (freq_max - freq_min) / duration_actual  # Hz/s

            # 250 ms windows → ~4 Hz freq resolution, fine time resolution
            nperseg = min(int(fs * 0.25), len(mag) // 8)
            noverlap = nperseg * 3 // 4
            f_sg, t_sg, Sxx = signal.spectrogram(
                mag, fs, nperseg=nperseg, noverlap=noverlap, window='hann'
            )

            sg_mask = (f_sg >= freq_min) & (f_sg <= freq_max)
            f_sg_r  = f_sg[sg_mask]
            Sxx_r   = Sxx[sg_mask, :]

            t_expected_sg = (f_sg_r - freq_min) / sweep_rate

            T_PEAK   = 0.5   # ±0.5 s peak window around expected excitation time
            T_BASE   = 1.5   # >1.5 s away from expected time → baseline region
            # Skip frequencies whose sweep time falls within the startup transient
            # zone (first T_MARGIN seconds).  The large initial acceleration burst
            # when the printer starts moving would score spuriously high for the
            # lowest frequencies in the range.
            T_MARGIN = 2.5   # seconds; skip f < freq_min + sweep_rate * T_MARGIN

            scores = np.zeros(len(f_sg_r))
            for i, t_e in enumerate(t_expected_sg):
                if t_e < T_MARGIN:
                    scores[i] = 0.0
                    continue
                row       = Sxx_r[i, :]
                t_pk_mask = np.abs(t_sg - t_e) <= T_PEAK
                t_bl_mask = np.abs(t_sg - t_e) >  T_BASE
                if np.any(t_pk_mask) and np.any(t_bl_mask):
                    pk = float(np.max(row[t_pk_mask]))
                    bl = float(np.mean(row[t_bl_mask])) + 1e-12
                    scores[i] = pk / bl

            if np.max(scores) > 0:
                sg_peak_i    = int(np.argmax(scores))
                sg_peak_freq = float(f_sg_r[sg_peak_i])

                # Refine with high-res FFT in ±5 Hz window around estimate
                refine_hz   = 5.0
                nearby_mask = (freq_r >= sg_peak_freq - refine_hz) & \
                              (freq_r <= sg_peak_freq + refine_hz)
                if np.any(nearby_mask):
                    nearby_idxs = np.where(nearby_mask)[0]
                    best_rel    = int(np.argmax(psd_r[nearby_mask]))
                    peak_idx    = int(nearby_idxs[best_rel])

                if debug:
                    raw_peak_freq = float(freq_r[int(np.argmax(psd_r))])
                    print(f'[sweep] Time-matched peak: {sg_peak_freq:.1f} Hz  '
                          f'score={scores[sg_peak_i]:.1f}  '
                          f'(raw FFT peak was {raw_peak_freq:.1f} Hz)')

    peak_freq  = float(freq_r[peak_idx])
    peak_power = float(psd_r[peak_idx])

    # ── 5. Parabolic interpolation for sub-bin precision ──────────────────────
    if 0 < peak_idx < len(psd_r) - 1:
        y0, y1, y2 = psd_r[peak_idx-1], psd_r[peak_idx], psd_r[peak_idx+1]
        denom = 2 * (2*y1 - y0 - y2)
        if denom != 0:
            delta     = (y2 - y0) / denom
            freq_step = float(freq_r[1] - freq_r[0]) if len(freq_r) > 1 else 0.0
            peak_freq = float(peak_freq + delta * freq_step)

    peak_freq = round(peak_freq, 1)

    # ── 6. Noise floor & SNR ──────────────────────────────────────────────────
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
        'frequency':   float(peak_freq),
        'confidence':  confidence,
        'q_factor':    float(round(snr, 1)),   # SNR used as quality proxy
        'snr':         float(round(snr, 1)),
        'sample_rate': float(round(fs, 1)),
        'error':       None,
    }


def analyze_multi_position_sweep(scans, belt_name='?', axis='',
                                  freq_min=85.0, freq_max=140.0,
                                  calibration=None, debug=False):
    """
    Analyze belt frequency from sweeps recorded at multiple Y positions.

    Two-stage algorithm:
      1. Structural fingerprint removal: any FFT peak that appears at the same
         frequency (within ±STRUCT_BIN) at two or more Y positions is a frame
         resonance and is excluded from belt candidate selection.
      2. Calibration-guided, closest-to-expected selection: among the remaining
         peaks within ±CALIB_WINDOW of the guitar-tuner calibration frequency
         for that Y position, pick the one CLOSEST to the expected value (not
         the strongest), so calibration accuracy steers the result past any
         residual structural peaks.

    Without calibration the function falls back to the single-position
    time-matched algorithm.

    Args:
        scans:       list of {'y_pos': float, 'filepath': str}
                     Must have ≥2 entries with distinct y_pos values.
        belt_name:   Label for logging ('A' or 'B').
        axis:        Scan axis string e.g. '1,-1'.
        freq_min:    Hz lower bound of scan range.
        freq_max:    Hz upper bound of scan range.
        calibration: list of {'y': float, 'freq': float} from guitar tuner.
                     Each entry gives the known belt frequency at one Y position.
        debug:       Print diagnostics if True.

    Returns dict (same shape as analyze_sweep_csv, plus extra fields):
        frequency        – float Hz at Y=100 (or nearest scanned position)
        confidence       – 'HIGH' / 'MEDIUM' / 'LOW' / 'UNRELIABLE'
        q_factor         – float SNR proxy
        snr              – float
        sample_rate      – float Hz
        error            – None or str
        method           – 'multi_position'
        position_results – list of {'y_pos','frequency','confidence','snr'}
        peak_mobility    – float Hz  (range of found frequencies across Y)
        classification   – 'belt' / 'ambiguous' / 'structural_only'
    """

    FAIL = lambda msg: {
        'frequency': None, 'confidence': None, 'q_factor': None,
        'snr': None, 'sample_rate': None, 'error': msg,
        'method': 'multi_position', 'position_results': [],
        'peak_mobility': 0.0, 'classification': 'structural_only',
    }

    # Search radius around calibration-expected frequency.  Wide enough to
    # catch slight calibration error, but used together with structural
    # exclusion + closest-to-expected selection so it doesn't need to be tight.
    CALIB_WINDOW = 12.0   # Hz, ±
    # Maximum frequency drift that still counts as "same resonance" across Y
    # positions.  Structural resonances drift <1-2 Hz; belt shifts 30-40 Hz.
    STRUCT_BIN   = 4.0    # Hz, ±

    if len(scans) < 2:
        return FAIL('Need at least 2 scan positions')

    scans = sorted(scans, key=lambda s: s['y_pos'])
    sample_rate = 0.0

    # ── Stage 1: Extract peaks and full results at every position ─────────────
    pos_data = []
    for scan in scans:
        peaks  = _extract_peaks(scan['filepath'], axis, freq_min, freq_max, n=15)
        full_r = analyze_sweep_csv(scan['filepath'], belt_name,
                                   freq_min, freq_max, axis, debug=False)
        if sample_rate == 0.0 and full_r.get('sample_rate'):
            sample_rate = full_r['sample_rate']
        pos_data.append({
            'y':     scan['y_pos'],
            'peaks': peaks,
            'full':  full_r,
        })

    # ── Stage 2: Identify structural fingerprints ─────────────────────────────
    # A frequency is "structural" if it appears within ±STRUCT_BIN at two or
    # more distinct Y positions.  Belt peaks move 30+ Hz across the Y range so
    # they are never flagged structural.
    structural_freqs = set()
    for i, pi in enumerate(pos_data):
        for fi, _ in pi['peaks']:
            for j in range(i + 1, len(pos_data)):
                pj = pos_data[j]
                for fj, _ in pj['peaks']:
                    if abs(fi - fj) <= STRUCT_BIN:
                        structural_freqs.add(fi)
                        structural_freqs.add(fj)
                        if debug:
                            print(f'[multi] Structural: {fi:.1f} Hz '
                                  f'(Y={pi["y"]:.0f}) <-> {fj:.1f} Hz '
                                  f'(Y={pj["y"]:.0f})')

    if debug and structural_freqs:
        print(f'[multi] Structural freqs: '
              f'{sorted(f"{f:.1f}" for f in structural_freqs)}')

    # ── Stage 3: At each position, select belt candidate ─────────────────────
    per_position = []
    for pd in pos_data:
        y     = pd['y']
        peaks = pd['peaks']

        chosen_freq = None
        chosen_snr  = None
        chosen_conf = None

        if calibration and peaks:
            expected = _interpolate_calibration(calibration, y)
            if expected is not None:
                # All peaks within the calibration search window
                in_window = [(f, p) for f, p in peaks
                             if abs(f - expected) <= CALIB_WINDOW]

                # Prefer non-structural candidates; fall back to full window
                # if structural exclusion empties the list.
                non_struct = [(f, p) for f, p in in_window
                              if not any(abs(f - sf) <= STRUCT_BIN
                                         for sf in structural_freqs)]
                candidates = non_struct if non_struct else in_window

                if candidates:
                    # Pick the candidate CLOSEST to expected (not strongest).
                    # This is more accurate when calibration is good and avoids
                    # preferring a nearby structural remnant that happens to be
                    # a few Hz closer but much stronger in raw power.
                    best_f, best_p = min(candidates,
                                         key=lambda x: abs(x[0] - expected))
                    chosen_freq   = best_f
                    estimated_snr = best_p * 20.0
                    chosen_snr    = round(estimated_snr, 1)
                    if estimated_snr > 15:   chosen_conf = 'HIGH'
                    elif estimated_snr > 7:  chosen_conf = 'MEDIUM'
                    elif estimated_snr > 3:  chosen_conf = 'LOW'
                    else:                    chosen_conf = 'UNRELIABLE'

                    if debug:
                        excl = [f'{f:.1f}' for f in structural_freqs
                                if abs(f - expected) <= CALIB_WINDOW]
                        print(f'[multi] Y={y:.0f}  expected={expected:.0f} Hz  '
                              f'chosen={chosen_freq:.1f} Hz (pwr={best_p:.2f})  '
                              f'candidates={[(f"{f:.1f}", f"{p:.2f}") for f, p in candidates[:4]]}  '
                              f'excl_struct={excl}')
                else:
                    if debug:
                        print(f'[multi] Y={y:.0f}  expected={expected:.0f} Hz  '
                              f'no peaks within ±{CALIB_WINDOW} Hz  '
                              f'top_peaks={[(f"{f:.1f}", f"{p:.2f}") for f, p in peaks[:5]]}')

        # Fall back to full-range time-matched result when calibration provides
        # no candidate.
        if chosen_freq is None:
            chosen_freq = pd['full'].get('frequency')
            chosen_snr  = pd['full'].get('snr')
            chosen_conf = pd['full'].get('confidence')
            if debug and calibration:
                print(f'[multi] Y={y:.0f}  fallback to time-matched: '
                      f'{chosen_freq} Hz  SNR={chosen_snr}')

        per_position.append({
            'y_pos':      y,
            'belt_freq':  chosen_freq,
            'snr':        chosen_snr,
            'confidence': chosen_conf,
            'full_result': pd['full'],
        })

    # ── Stage 4: Report frequency at Y=100 ────────────────────────────────────
    y100_list = [p for p in per_position if p['y_pos'] == 100.0]
    report = y100_list[0] if y100_list else \
             min(per_position, key=lambda p: abs(p['y_pos'] - 100.0))

    belt_freq = report['belt_freq']
    belt_snr  = report['snr']
    belt_conf = report['confidence']

    if belt_freq is None:
        return _fallback_single_position(
            [{'y_pos': p['y_pos'], 'single': p['full_result']} for p in per_position],
            belt_name
        )

    # ── Stage 5: Mobility and classification ──────────────────────────────────
    valid_freqs = [p['belt_freq'] for p in per_position if p['belt_freq'] is not None]
    mobility = round(max(valid_freqs) - min(valid_freqs), 1) if len(valid_freqs) >= 2 else 0.0

    # Belt peaks shift ~36 Hz from Y=80 to Y=120 (inverse string law).
    # Require at least 40% of the expected calibration shift before calling it
    # 'belt'; any less and we may just be tracking a structural resonance that
    # crept inside the calibration window.
    if calibration and len(scans) >= 2:
        y_vals    = [s['y_pos'] for s in scans]
        exp_freqs = [_interpolate_calibration(calibration, y) for y in y_vals]
        exp_freqs = [f for f in exp_freqs if f is not None]
        exp_mob   = max(exp_freqs) - min(exp_freqs) if len(exp_freqs) >= 2 else 30.0
        classification = 'belt' if mobility >= exp_mob * 0.4 else 'ambiguous'
    else:
        classification = 'belt' if mobility >= 10.0 else 'ambiguous'

    if debug:
        print(f'[multi] Belt {belt_name}: {belt_freq} Hz  SNR={belt_snr}  '
              f'{belt_conf}  class={classification}  mobility={mobility} Hz')

    return {
        'frequency':        float(round(belt_freq, 1)),
        'confidence':       belt_conf,
        'q_factor':         float(round(belt_snr, 1)) if belt_snr is not None else None,
        'snr':              float(round(belt_snr, 1)) if belt_snr is not None else None,
        'sample_rate':      float(round(sample_rate, 1)),
        'error':            None,
        'method':           'multi_position',
        'position_results': [
            {'y_pos':      p['y_pos'],
             'frequency':  p['belt_freq'],
             'confidence': p['confidence'],
             'snr':        p['snr']}
            for p in per_position
        ],
        'peak_mobility':    mobility,
        'classification':   classification,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: belt_sweep_analyzer.py <csv_file> [freq_min] [freq_max] [axis]')
        sys.exit(1)
    fmin  = float(sys.argv[2]) if len(sys.argv) > 2 else 85.0
    fmax  = float(sys.argv[3]) if len(sys.argv) > 3 else 140.0
    aaxis = sys.argv[4]        if len(sys.argv) > 4 else ''
    result = analyze_sweep_csv(sys.argv[1], freq_min=fmin, freq_max=fmax,
                               axis=aaxis, debug=True)
    if result['error']:
        print(f'Error: {result["error"]}')
    else:
        print(f'Frequency: {result["frequency"]} Hz')
        print(f'Confidence: {result["confidence"]}  SNR: {result["snr"]}')
