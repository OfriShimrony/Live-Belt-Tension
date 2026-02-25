"""
Belt Trend Analysis — Multi-position diagonal sweep heatmap.

Key idea:
  - Structural resonances appear as VERTICAL bands (same Hz at all positions)
  - Belt string resonances appear as DIAGONAL bands (Hz shifts with position)
  - The phone-measured trend lines are overlaid as ground truth

Expected CSVs in tests/ (download from /tmp/ on printer):
  raw_data_trend_a_p125.csv  ...p150  ...p175  ...p200  ...p225
  raw_data_trend_b_p125.csv  ...p150  ...p175  ...p200  ...p225

G-code:
  TEST_RESONANCES AXIS=1,-1 OUTPUT=raw_data NAME=trend_a_p125 FREQ_START=55 FREQ_END=135 HZ_PER_SEC=1 POINT=125,125,20
  TEST_RESONANCES AXIS=1,-1 OUTPUT=raw_data NAME=trend_a_p150 FREQ_START=55 FREQ_END=135 HZ_PER_SEC=1 POINT=150,150,20
  TEST_RESONANCES AXIS=1,-1 OUTPUT=raw_data NAME=trend_a_p175 FREQ_START=55 FREQ_END=135 HZ_PER_SEC=1 POINT=175,175,20
  TEST_RESONANCES AXIS=1,-1 OUTPUT=raw_data NAME=trend_a_p200 FREQ_START=55 FREQ_END=135 HZ_PER_SEC=1 POINT=200,200,20
  TEST_RESONANCES AXIS=1,-1 OUTPUT=raw_data NAME=trend_a_p225 FREQ_START=55 FREQ_END=135 HZ_PER_SEC=1 POINT=225,225,20
  (same with AXIS=1,1 and belt_b names)
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import signal

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

POSITIONS = [125, 150, 175, 200, 225]   # diagonal positions (X=Y)
FREQ_RANGE = (55, 135)                   # Hz — plot window

# Phone-measured reference frequencies at 110 Hz tension.
# Format: pos -> {belt -> {segment -> Hz}}
PHONE_REF = {
    125: {'A': {'right': 68,  'left': 108}, 'B': {'right': 64,  'left': 118}},
    150: {'A': {'right': 76,  'left': 93 }, 'B': {'right': 72,  'left': 100}},
    175: {'A': {'right': 85,  'left': 81 }, 'B': {'right': 78,  'left': 85 }},
    200: {'A': {'right': 104, 'left': 74 }, 'B': {'right': 91,  'left': 75 }},
    225: {'A': {'right': 125, 'left': 67 }, 'B': {'right': 102, 'left': 65 }},
}


def load_csv(filepath):
    times, ax, ay, az = [], [], [], []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) < 4:
                continue
            try:
                times.append(float(parts[0]))
                ax.append(float(parts[1]))
                ay.append(float(parts[2]))
                az.append(float(parts[3]))
            except ValueError:
                continue
    return np.array(times), np.array(ax), np.array(ay), np.array(az)


def compute_psd(times, ax, ay, az):
    mag = np.sqrt(ax**2 + ay**2 + az**2)
    dt = np.diff(times)
    dt = dt[dt > 0]
    fs = 1.0 / np.median(dt)
    nperseg = min(int(fs * 2), len(mag))
    freqs, psd = signal.welch(mag, fs=fs, nperseg=nperseg, noverlap=nperseg // 2,
                               window='hann', scaling='density')
    return freqs, psd


def build_heatmap(belt_label):
    """
    Returns (freq_axis, psd_matrix, loaded_positions).
    psd_matrix shape: (n_positions, n_freqs), each row normalized 0-1.
    """
    freq_axis = None
    rows = []
    loaded = []

    for pos in POSITIONS:
        fname = f'raw_data_trend_{"a" if belt_label == "A" else "b"}_p{pos}.csv'
        fpath = os.path.join(TESTS_DIR, fname)

        if not os.path.exists(fpath):
            print(f'  [MISSING] {fname}')
            rows.append(None)
            loaded.append(False)
            continue

        times, bx, by, bz = load_csv(fpath)
        freqs, psd = compute_psd(times, bx, by, bz)

        if freq_axis is None:
            freq_axis = freqs

        # Interpolate to common frequency axis if needed
        if len(freqs) != len(freq_axis) or not np.allclose(freqs, freq_axis):
            psd = np.interp(freq_axis, freqs, psd)

        # Crop to FREQ_RANGE
        mask = (freq_axis >= FREQ_RANGE[0]) & (freq_axis <= FREQ_RANGE[1])
        psd_crop = psd[mask]

        # Normalize row to 0-1
        m = np.max(psd_crop)
        psd_norm = psd_crop / m if m > 0 else psd_crop

        rows.append(psd_norm)
        loaded.append(True)
        print(f'  Belt {belt_label} pos={pos}: loaded ({len(times)} samples, '
              f'fs={1/np.median(np.diff(times[times>0])):.0f} Hz)')

    if freq_axis is None:
        return None, None, []

    freq_crop = freq_axis[(freq_axis >= FREQ_RANGE[0]) & (freq_axis <= FREQ_RANGE[1])]

    # Replace missing rows with zeros
    n_freqs = len(freq_crop)
    matrix = np.zeros((len(POSITIONS), n_freqs))
    for i, row in enumerate(rows):
        if row is not None:
            matrix[i] = row

    return freq_crop, matrix, loaded


def plot_heatmap(ax_heat, ax_lines, belt_label, freq_axis, matrix, loaded):
    """
    ax_heat: 2D heatmap (frequency vs position)
    ax_lines: overlay of individual PSDs as line plot
    """
    pos_arr = np.array(POSITIONS)

    # --- Heatmap ---
    ax_heat.imshow(
        matrix,
        aspect='auto',
        origin='lower',
        extent=[FREQ_RANGE[0], FREQ_RANGE[1], 0, len(POSITIONS)],
        cmap='inferno',
        vmin=0, vmax=1,
        interpolation='nearest',
    )
    ax_heat.set_yticks(np.arange(len(POSITIONS)) + 0.5)
    ax_heat.set_yticklabels([f'({p},{p})' for p in POSITIONS], fontsize=8)
    ax_heat.set_xlabel('Frequency (Hz)')
    ax_heat.set_ylabel('Toolhead position (X=Y diagonal)')
    ax_heat.set_title(f'Belt {belt_label} — Heatmap\nVertical=structural, Diagonal=belt string')

    # Overlay phone reference trend lines on heatmap
    right_freqs = [PHONE_REF[p][belt_label]['right'] for p in POSITIONS]
    left_freqs  = [PHONE_REF[p][belt_label]['left']  for p in POSITIONS]
    y_centers   = np.arange(len(POSITIONS)) + 0.5

    ax_heat.plot(right_freqs, y_centers, 'o--', color='lime',   linewidth=1.5,
                 markersize=5, label='Phone: right segment', zorder=5)
    ax_heat.plot(left_freqs,  y_centers, 's--', color='cyan',   linewidth=1.5,
                 markersize=5, label='Phone: left segment',  zorder=5)
    ax_heat.legend(loc='upper right', fontsize=7)

    # --- Line overlay ---
    colors = plt.cm.plasma(np.linspace(0.1, 0.9, len(POSITIONS)))
    for i, (pos, color, ok) in enumerate(zip(POSITIONS, colors, loaded)):
        if ok:
            ax_lines.plot(freq_axis, matrix[i], color=color, linewidth=1.2,
                          alpha=0.85, label=f'({pos},{pos})')

    # Phone reference lines (vertical markers at each position's expected freq)
    # Show as small tick marks
    for i, pos in enumerate(POSITIONS):
        r = PHONE_REF[pos][belt_label]['right']
        l = PHONE_REF[pos][belt_label]['left']
        y_norm = (i + 0.5) / len(POSITIONS)   # not used here, just show as vlines
        ax_lines.axvline(r, color='lime', linewidth=0.6, alpha=0.4)
        ax_lines.axvline(l, color='cyan', linewidth=0.6, alpha=0.4)

    ax_lines.set_xlim(*FREQ_RANGE)
    ax_lines.set_ylim(0, 1.1)
    ax_lines.set_xlabel('Frequency (Hz)')
    ax_lines.set_ylabel('Normalised PSD')
    ax_lines.set_title(f'Belt {belt_label} — Individual PSDs\n'
                       'Green ticks=phone right, Cyan ticks=phone left')
    ax_lines.legend(loc='upper right', fontsize=7, title='Position')
    ax_lines.grid(True, alpha=0.25)


def assess_trend(belt_label, freq_axis, matrix, loaded):
    """Check if any detected peak follows the phone trend line."""
    print(f'\n  Belt {belt_label} trend assessment:')
    right_ref = [PHONE_REF[p][belt_label]['right'] for p in POSITIONS]
    left_ref  = [PHONE_REF[p][belt_label]['left']  for p in POSITIONS]

    right_hits, left_hits = 0, 0
    total = sum(loaded)

    for i, (pos, ok) in enumerate(zip(POSITIONS, loaded)):
        if not ok:
            continue
        row = matrix[i]
        # Find top peaks in this row
        psd_in_range = row
        peaks_idx, _ = signal.find_peaks(psd_in_range, height=0.1,
                                          distance=max(1, int(len(row) / (FREQ_RANGE[1] - FREQ_RANGE[0]))))
        peak_freqs = freq_axis[peaks_idx]

        r = right_ref[i]
        l = left_ref[i]
        r_match = any(abs(pf - r) <= 5 for pf in peak_freqs)
        l_match = any(abs(pf - l) <= 5 for pf in peak_freqs)
        right_hits += r_match
        left_hits  += l_match

        status = []
        if r_match: status.append(f'right HIT ({r} Hz)')
        if l_match: status.append(f'left HIT ({l} Hz)')
        if not status: status = [f'no match (ref: right={r}, left={l} Hz)']
        print(f'    pos ({pos},{pos}): {", ".join(status)}')

    print(f'  Right segment trend: {right_hits}/{total} positions matched')
    print(f'  Left  segment trend: {left_hits}/{total} positions matched')

    if right_hits >= 3 or left_hits >= 3:
        print(f'  --> TREND DETECTED: ADXL can track belt string resonance for Belt {belt_label}')
    elif right_hits >= 1 or left_hits >= 1:
        print(f'  --> WEAK SIGNAL: partial trend, needs investigation')
    else:
        print(f'  --> NO TREND: structural resonances dominate, belt string not visible')


def main():
    print('Belt Trend Analysis — Multi-position diagonal sweep')
    print(f'Looking for CSVs in: {TESTS_DIR}')
    print()

    fig = plt.figure(figsize=(15, 10))
    fig.suptitle('Belt Diagonal Sweep — Frequency vs Position Heatmap\n'
                 'Structural peaks = vertical bands | Belt string peaks = diagonal bands\n'
                 'Lime = phone right segment, Cyan = phone left segment',
                 fontsize=11)

    gs = gridspec.GridSpec(2, 2, hspace=0.5, wspace=0.35)
    ax_a_heat  = fig.add_subplot(gs[0, 0])
    ax_a_lines = fig.add_subplot(gs[0, 1])
    ax_b_heat  = fig.add_subplot(gs[1, 0])
    ax_b_lines = fig.add_subplot(gs[1, 1])

    print('--- Belt A ---')
    freq_a, matrix_a, loaded_a = build_heatmap('A')
    if freq_a is not None:
        plot_heatmap(ax_a_heat, ax_a_lines, 'A', freq_a, matrix_a, loaded_a)
        assess_trend('A', freq_a, matrix_a, loaded_a)
    else:
        print('  No Belt A data found.')

    print()
    print('--- Belt B ---')
    freq_b, matrix_b, loaded_b = build_heatmap('B')
    if freq_b is not None:
        plot_heatmap(ax_b_heat, ax_b_lines, 'B', freq_b, matrix_b, loaded_b)
        assess_trend('B', freq_b, matrix_b, loaded_b)
    else:
        print('  No Belt B data found.')

    print()
    plt.tight_layout()
    out_path = os.path.join(TESTS_DIR, 'trend_heatmap.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f'Plot saved: {out_path}')
    plt.show()


if __name__ == '__main__':
    main()
