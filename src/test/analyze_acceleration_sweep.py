#!/usr/bin/env python3
"""
Acceleration Sweep Batch Analyzer
----------------------------------
Analyzes all acceleration test results and finds optimal acceleration.

Usage:
    python3 analyze_acceleration_sweep.py <belt>
    
Examples:
    python3 analyze_acceleration_sweep.py a
    python3 analyze_acceleration_sweep.py b
"""

import sys
import os
import glob
from belt_analysis_complete import analyze_belt_with_full_pipeline

def analyze_sweep(belt):
    """Analyze all acceleration sweep results"""
    
    belt_name = f"Belt {belt.upper()}"
    
    print("="*70)
    print("ACCELERATION SWEEP ANALYSIS")
    print("="*70)
    print(f"Belt: {belt_name}")
    print()
    
    # Find all sweep files
    pattern = f"/tmp/adxl345-accel_sweep_{belt}_*.csv"
    files = sorted(glob.glob(pattern))
    
    if not files:
        print(f"✗ No sweep data found!")
        print(f"  Looking for: {pattern}")
        print()
        print("Run the sweep test first:")
        print(f"  python3 acceleration_sweep_test.py {belt}")
        return
    
    print(f"Found {len(files)} test files")
    print()
    print("="*70)
    
    results = []
    
    for filepath in files:
        # Extract acceleration from filename
        filename = os.path.basename(filepath)
        # Format: adxl345-accel_sweep_a_1000.csv
        parts = filename.replace('.csv', '').split('_')
        accel = int(parts[-1])
        
        print(f"\nAcceleration: {accel} mm/s²")
        print("-"*70)
        
        result = analyze_belt_with_full_pipeline(filepath, f"{belt_name} @ {accel} mm/s²")
        
        if 'error' not in result:
            result['acceleration'] = accel
            results.append(result)
        
        print()
    
    # Summary comparison
    print("\n" + "="*70)
    print("SUMMARY COMPARISON")
    print("="*70)
    print()
    print("Accel     Frequency   Q-Factor   SNR    Score  Confidence")
    print("-"*70)
    
    best_score = 0
    best_accel = None
    
    for r in results:
        accel = r['acceleration']
        freq = r['frequency']
        q = r['q_factor']
        snr = r['snr']
        score = r['score']
        conf = r['confidence']
        
        marker = ""
        if score > best_score:
            best_score = score
            best_accel = accel
            marker = " ⭐"
        
        print(f"{accel:5d}     {freq:6.1f} Hz   Q={q:5.1f}   {snr:4.1f}x   {score:2d}/10  {conf:6s}{marker}")
    
    print()
    print("="*70)
    
    if best_accel:
        print(f"✓ BEST ACCELERATION: {best_accel} mm/s²")
        print(f"  (Highest confidence score: {best_score}/10)")
        
        # Find the result for best acceleration
        best_result = next(r for r in results if r['acceleration'] == best_accel)
        
        print()
        print("Recommended settings:")
        print(f"  Acceleration: {best_accel} mm/s²")
        print(f"  Expected frequency: {best_result['frequency']:.1f} Hz")
        print(f"  Signal quality: {best_result['confidence']}")
    else:
        print("⚠ No clear winner - all signals have low confidence")
        print()
        print("Possible issues:")
        print("  - Belt may not be vibrating (too tight or friction)")
        print("  - Movement too small (try 30-50mm instead of 20mm)")
        print("  - Need different approach (manual pluck detection)")
    
    print()
    print("="*70)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_acceleration_sweep.py <belt>")
        print()
        print("Examples:")
        print("  python3 analyze_acceleration_sweep.py a")
        print("  python3 analyze_acceleration_sweep.py b")
        sys.exit(1)
    
    belt = sys.argv[1].lower()
    
    if belt not in ['a', 'b']:
        print("Belt must be 'a' or 'b'")
        sys.exit(1)
    
    analyze_sweep(belt)

if __name__ == "__main__":
    main()
