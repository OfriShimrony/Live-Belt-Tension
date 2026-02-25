"""
Diagonal Sweep Analysis — Can the ADXL detect individual belt segment frequencies?

Loads raw TEST_RESONANCES CSVs (one per belt per position) and computes the PSD.
Marks the phone-measured reference frequencies so we can see if ADXL peaks align.

Usage:
    python tests/analyze_diagonal_sweep.py

Expected CSV files in tests/ (download from /tmp/ on printer):
    raw_data_diag_a_center.csv   -- Belt A sweep, toolhead at (175,175)
    raw_data_diag_b_center.csv   -- Belt B sweep, toolhead at (175,175)
    raw_data_diag_a_125.csv      -- Belt A sweep, toolhead at (125,125)
    raw_data_diag_b_125.csv      -- Belt B sweep, toolhead at (125,125)

Phone-measured reference (110 Hz tension, your printer):
    Position (175,175): A-right=85, A-left=81, B-right=78, B-left=85 Hz
    Position (125,125): A-right=68, A-left=108, B-right=64, B-left=118 Hz

G-code to generate:
    TEST_RESONANCES AXIS=1,-1 OUTPUT=raw_data NAME=diag_a_center FREQ_START=60 FREQ_END=130 HZ_PER_SEC=1 POINT=175,175,20
    TEST_RESONANCES AXIS=1,1  OUTPUT=raw_data NAME=diag_b_center FREQ_START=60 FREQ_END=130 HZ_PER_SEC=1 POINT=175,175,20
    TEST_RESONANCES AXIS=1,-1 OUTPUT=raw_data NAME=diag_a_125   FREQ_START=55 FREQ_END=130 HZ_PER_SEC=1 POINT=125,125,20
    TEST_RESONANCES AXIS=1,1  OUTPUT=raw_data NAME=diag_b_125   FREQ_START=55 FREQ_END=130 HZ_PER_SEC=1 POINT=125,125,20
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import signal

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Phone-measured reference frequencies (110 Hz tension)
PHONE_REF = {
    'center': {
        'A': {'right': 85, 'left': 81},
        'B': {'right': 78, 'left': 85},
        'position': '(175,175)',
    },
    '125': {
        'A': {'right': 68, 'left': 108},
        'B': {'right': 64, 'left': 118},
        'position': '(125,125)',
    },
}

DATASETS = [
    # (csv_name, belt_label, position_key, color)
    ('raw_data_diag_a_center.csv', 'A', 'center', '#e74c3c'),
    ('raw_data_diag_b_center.csv', 'B', 'center', '#2980b9'),
    ('raw_data_diag_a_125.csv',    'A', '125',    '#c0392b'),
    ('raw_data_diag_b_125.csv',    'B', '125',    '#1a5276'),
]


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
    nperseg = min(int(fs * 2), len(mag))   # 2-second windows for ~0.5 Hz resolution
    freqs, psd = signal.welch(mag, fs=fs, nperseg=nperseg, noverlap=nperseg // 2,
                               window='hann', scaling='density')
    return freqs, psd, fs


def normalize(psd):
    m = np.max(psd)
    return psd / m if m > 0 else psd


def find_peaks(freqs, psd_norm, fmin=55, fmax=130):
    mask = (freqs >= fmin) & (freqs <= fmax)
    f_r = freqs[mask]
    p_r = psd_norm[mask]
    if len(p_r) == 0:
        return []
    idx, _ = signal.find_peaks(p_r, height=0.05, distance=max(1, int(len(f_r) / (fmax - fmin))))
    heights = p_r[idx]
    order = np.argsort(heights)[::-1][:6]
    return sorted([(f_r[idx[i]], heights[i]) for i in order], key=lambda x: x[0])


def plot_position(axes, pos_key, fmin=55, fmax=130):
    ref = PHONE_REF[pos_key]
    pos_label = ref['position']

    for belt in ['A', 'B']:
        fname = f'raw_data_diag_{"a" if belt=="A" else "b"}_{pos_key}.csv'
        fpath = os.path.join(TESTS_DIR, fname)
        ax_plot = axes[0] if belt == 'A' else axes[1]
        color = '#c0392b' if belt == 'A' else '#1a5276'

        if not os.path.exists(fpath):
            ax_plot.text(0.5, 0.5, f'{fname}\nNOT FOUND',
                         ha='center', va='center', transform=ax_plot.transAxes,
                         color='red', fontsize=10)
            ax_plot.set_title(f'Belt {belt} — {pos_label}  [MISSING]')
            continue

        times, bx, by, bz = load_csv(fpath)
        freqs, psd, fs = compute_psd(times, bx, by, bz)
        psd_norm = normalize(psd)

        mask = (freqs >= fmin) & (freqs <= fmax)
        ax_plot.plot(freqs[mask], psd_norm[mask], color=color, linewidth=1.5, alpha=0.9,
                     label=f'Belt {belt} ADXL (AXIS={"1,-1" if belt=="A" else "1,1"})')

        # Mark phone-reference frequencies
        r_freq = ref[belt]['right']
        l_freq = ref[belt]['left']
        ax_plot.axvline(r_freq, color='green', linewidth=1.2, linestyle='--', alpha=0.8)
        ax_plot.axvline(l_freq, color='orange', linewidth=1.2, linestyle='--', alpha=0.8)
        ax_plot.text(r_freq + 0.5, 0.97, f'{belt}-right\n{r_freq} Hz',
                     color='green', fontsize=7, va='top',
                     transform=ax_plot.get_xaxis_transform())
        ax_plot.text(l_freq + 0.5, 0.80, f'{belt}-left\n{l_freq} Hz',
                     color='orange', fontsize=7, va='top',
                     transform=ax_plot.get_xaxis_transform())

        # Find ADXL peaks and print comparison
        peaks = find_peaks(freqs, psd_norm, fmin, fmax)
        print(f'  Belt {belt} @ {pos_label}: top ADXL peaks = '
              + ', '.join(f'{f:.1f} Hz ({h:.0%})' for f, h in peaks[:5]))
        print(f'    Phone ref: right={r_freq} Hz, left={l_freq} Hz')

        # Check if any peak is within 5 Hz of a phone reference
        matches = []
        for pf, ph in peaks:
            for label, ref_f in [('right', r_freq), ('left', l_freq)]:
                if abs(pf - ref_f) <= 5:
                    matches.append(f'{label} ({ref_f} Hz → ADXL peak at {pf:.1f} Hz, Δ={pf-ref_f:+.1f})')
        if matches:
            print(f'    MATCHES: {", ".join(matches)}')
        else:
            print(f'    NO MATCH within ±5 Hz of either reference frequency')
        print()

        ax_plot.set_title(f'Belt {belt} diagonal sweep — {pos_label}')
        ax_plot.set_xlim(fmin, fmax)
        ax_plot.set_ylim(0, 1.1)
        ax_plot.set_ylabel('Normalised PSD')
        ax_plot.legend(loc='upper left', fontsize=8)
        ax_plot.grid(True, alpha=0.3)

    axes[1].set_xlabel('Frequency (Hz)')


def print_verdict(results):
    print('=' * 60)
    print('VERDICT — Can ADXL detect belt segment frequencies?')
    print('=' * 60)
    any_match = any(results.values())
    if any_match:
        print('POSITIVE: At least one ADXL peak aligns with a phone-')
        print('measured belt segment frequency. Worth pursuing further.')
    else:
        print('NEGATIVE: No ADXL peaks align with phone-measured belt')
        print('segment frequencies. ADXL sweep is not sensitive to')
        print('transverse string resonance at these conditions.')
    print()
    print('Next steps if POSITIVE:')
    print('  - Try different toolhead positions')
    print('  - Try ACCEL_PER_HZ variations to change excitation strength')
    print('  - Look at individual axes (x/y) instead of magnitude')
    print()
    print('Next steps if NEGATIVE:')
    print('  - Consider pluck-triggered ADXL capture instead of sweep')
    print('  - Or continue with phone-app approach as gold standard')


def main():
    print('Diagonal Sweep Analysis — ADXL vs Phone Reference')
    print(f'CSV directory: {TESTS_DIR}')
    print()

    fig = plt.figure(figsize=(14, 10))
    fig.suptitle('Diagonal Belt Sweep — ADXL PSD vs Phone-Measured Segment Frequencies\n'
                 'Green dashed = phone right-segment, Orange dashed = phone left-segment',
                 fontsize=11)

    gs = gridspec.GridSpec(2, 2, hspace=0.45, wspace=0.3)
    ax_a_center = fig.add_subplot(gs[0, 0])
    ax_b_center = fig.add_subplot(gs[1, 0])
    ax_a_125    = fig.add_subplot(gs[0, 1])
    ax_b_125    = fig.add_subplot(gs[1, 1])

    print('--- Center (175,175) ---')
    plot_position([ax_a_center, ax_b_center], 'center', fmin=60, fmax=130)

    print('--- Off-center (125,125) ---')
    plot_position([ax_a_125, ax_b_125], '125', fmin=55, fmax=130)

    # Add column headers
    ax_a_center.set_title('Center (175,175) — Belt A\n' + ax_a_center.get_title().split('—')[-1])
    ax_a_125.set_title('Off-center (125,125) — Belt A\n' + ax_a_125.get_title().split('—')[-1])

    plt.tight_layout()
    out_path = os.path.join(TESTS_DIR, 'diagonal_sweep_plot.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f'Plot saved: {out_path}')
    plt.show()


if __name__ == '__main__':
    main()
