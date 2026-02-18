#!/usr/bin/env python3
"""
CoreXY Belt Tension Tuner - Klipper Macro Handler
===================================================
Orchestrates ADXL345 measurements via Moonraker and analyzes
results using belt_analyzer_v3.

Usage (called by gcode_shell_command):
    python3 belt_tuner.py BELT=A     # Measure Belt A (3 plucks, averaged)
    python3 belt_tuner.py BELT=B     # Measure Belt B
    python3 belt_tuner.py COMPARE    # Measure and compare both belts
"""

import requests
import time
import sys
import os

MOONRAKER_URL = "http://localhost:7125"

# Import V3 analyzer — search common install locations
_SEARCH_PATHS = [
    os.path.dirname(os.path.abspath(__file__)),
    os.path.expanduser("~/Live-Belt-Tension/src"),
]
for _p in _SEARCH_PATHS:
    if os.path.exists(os.path.join(_p, "belt_analyzer_v3.py")):
        sys.path.insert(0, _p)
        break

from belt_analyzer_v3 import analyze_pluck_event as _analyze_v3


def send_gcode(command):
    """Send G-code command to Klipper via Moonraker."""
    try:
        url = f"{MOONRAKER_URL}/printer/gcode/script"
        params = {"script": command}
        response = requests.post(url, params=params, timeout=10)
        return response.status_code == 200
    except:
        return False


def respond_msg(message):
    """Send message to Klipper console and stdout."""
    send_gcode(f'RESPOND MSG="{message}"')
    print(message)


def find_latest_csv():
    """Find most recent ADXL CSV file in /tmp."""
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


def analyze_pluck(filepath):
    """Analyze a single belt pluck using the V3 analyzer."""
    return _analyze_v3(filepath)


def measure_belt_multi(belt_name, num_measurements=3):
    """
    Measure belt frequency multiple times and average with outlier rejection.

    Returns dict with frequency, confidence, measurements, or error.
    """
    import numpy as np

    respond_msg(f"=== Belt {belt_name} Measurement ===")
    respond_msg(f"Will take {num_measurements} measurements")
    respond_msg("")

    measurements = []

    for i in range(num_measurements):
        respond_msg(f"Measurement {i+1}/{num_measurements}")
        respond_msg("Pluck the belt in:")

        for j in range(3, 0, -1):
            respond_msg(f"  {j}...")
            time.sleep(0.8)

        respond_msg("  >>> PLUCK NOW! <<<")

        send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
        time.sleep(0.3)

        time.sleep(3.0)

        send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=belt_{belt_name}_{i+1}")
        time.sleep(0.5)

        csv_file = find_latest_csv()

        if csv_file:
            result = analyze_pluck(csv_file)
            if 'error' not in result:
                freq = result['frequency']
                q = result['q_factor']
                conf = result['confidence']
                respond_msg(f"  Result: {freq:.1f} Hz (Q={q:.0f}, {conf})")
                measurements.append(result)
            else:
                respond_msg(f"  Error: {result['error']}")
        else:
            respond_msg("  No data file found")

        if i < num_measurements - 1:
            respond_msg("")
            time.sleep(1.0)

    respond_msg("")
    respond_msg("-" * 40)

    if len(measurements) == 0:
        respond_msg("No valid measurements")
        return {'error': 'No valid measurements'}

    if len(measurements) == 1:
        result = measurements[0]
        respond_msg(f"Belt {belt_name}: {result['frequency']:.1f} Hz ({result['confidence']})")
        return {
            'belt': belt_name,
            'frequency': result['frequency'],
            'confidence': result['confidence'],
            'measurements': measurements,
        }

    # Filter by Q-factor (keep Q > 5)
    good = [m for m in measurements if m['q_factor'] > 5] or measurements

    # Filter outliers by median if high spread
    if len(good) >= 2:
        freqs = [m['frequency'] for m in good]
        if np.std(freqs) > 5:
            median = np.median(freqs)
            good = [m for m in good if abs(m['frequency'] - median) < 10] or good

    final_freq = float(np.mean([m['frequency'] for m in good]))
    avg_q = float(np.mean([m['q_factor'] for m in good]))

    if avg_q > 50:
        final_conf = "EXCELLENT"
    elif avg_q > 20:
        final_conf = "HIGH"
    else:
        final_conf = "GOOD"

    respond_msg(f"Belt {belt_name} Final: {final_freq:.1f} Hz ({final_conf})")
    respond_msg(f"  Based on {len(good)}/{len(measurements)} measurements")
    if len(good) < len(measurements):
        respond_msg(f"  ({len(measurements) - len(good)} outlier(s) rejected)")

    return {
        'belt': belt_name,
        'frequency': final_freq,
        'confidence': final_conf,
        'q_factor': avg_q,
        'measurements': measurements,
        'good_count': len(good),
        'total_count': len(measurements),
    }


def compare_belts():
    """Measure and compare both belts."""
    respond_msg("=" * 50)
    respond_msg("BELT COMPARISON")
    respond_msg("=" * 50)
    respond_msg("")

    result_a = measure_belt_multi('A', num_measurements=3)

    respond_msg("")
    time.sleep(2)

    result_b = measure_belt_multi('B', num_measurements=3)

    respond_msg("")
    respond_msg("=" * 50)
    respond_msg("COMPARISON RESULTS")
    respond_msg("=" * 50)

    if 'error' in result_a or 'error' in result_b:
        respond_msg("Cannot compare - measurement failed")
        return

    freq_a = result_a['frequency']
    freq_b = result_b['frequency']
    delta = abs(freq_a - freq_b)

    respond_msg(f"Belt A: {freq_a:.1f} Hz ({result_a['confidence']})")
    respond_msg(f"Belt B: {freq_b:.1f} Hz ({result_b['confidence']})")
    respond_msg(f"Delta:  {delta:.1f} Hz")
    respond_msg("")

    if delta < 2:
        respond_msg("EXCELLENT - Belts are well matched!")
    elif delta < 5:
        respond_msg("GOOD - Belts are acceptably matched")
    elif delta < 10:
        respond_msg("FAIR - Consider adjusting")
    else:
        respond_msg("POOR - Belts need adjustment")

    respond_msg("=" * 50)


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 belt_tuner.py BELT=A     # Measure Belt A")
        print("  python3 belt_tuner.py BELT=B     # Measure Belt B")
        print("  python3 belt_tuner.py COMPARE    # Compare both belts")
        sys.exit(1)

    command = sys.argv[1].upper()

    if command == "COMPARE":
        compare_belts()
    elif command.startswith("BELT="):
        belt = command.split("=")[1]
        if belt not in ['A', 'B']:
            print("Belt must be A or B")
            sys.exit(1)
        measure_belt_multi(belt, num_measurements=3)
    else:
        print("Unknown command. Use BELT=A, BELT=B, or COMPARE")
        sys.exit(1)


if __name__ == "__main__":
    main()
