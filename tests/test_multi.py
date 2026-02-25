"""Quick test of analyze_multi_position_sweep with same CSV at all 3 Y positions."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from belt_sweep_analyzer import analyze_multi_position_sweep

D = os.path.dirname(__file__)

CALIB_A = [{'y': 80, 'freq': 134}, {'y': 100, 'freq': 110}, {'y': 120, 'freq': 98}]
CALIB_B = [{'y': 80, 'freq': 135}, {'y': 100, 'freq': 110}, {'y': 120, 'freq': 101}]

def run(label, axis, calib):
    scans = [
        {'y_pos':  80.0, 'filepath': os.path.join(D, f'raw_data_belt_{label.lower()}_y80.csv')},
        {'y_pos': 100.0, 'filepath': os.path.join(D, f'raw_data_belt_{label.lower()}_y100.csv')},
        {'y_pos': 120.0, 'filepath': os.path.join(D, f'raw_data_belt_{label.lower()}_y120.csv')},
    ]
    print(f'=== Belt {label} (real 3-position scans) ===')
    r = analyze_multi_position_sweep(scans, label, axis=axis, calibration=calib, debug=True)
    print(f'--> {r["frequency"]} Hz  conf={r["confidence"]}  '
          f'class={r["classification"]}  mobility={r["peak_mobility"]} Hz')
    print(f'    pos_results: {[(p["y_pos"], p["frequency"]) for p in r["position_results"]]}')
    print()

run('A', '1,-1', CALIB_A)
run('B', '1,1',  CALIB_B)
