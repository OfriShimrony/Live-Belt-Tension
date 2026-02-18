#!/usr/bin/env python3
"""
Improved Acceleration Sweep Analyzer
-------------------------------------
Analyzes results from the improved pluck-and-decay test.

Usage:
    python3 analyze_improved_sweep.py <belt>
"""

import sys
import glob
from belt_analysis_complete import analyze_belt_with_full_pipeline

def analyze_improved_sweep(belt):
    """Analyze improved acceleration sweep results"""
    
    belt_name = f"Belt {belt.upper()}"
    
    print("="*70)
    print("IMPROVED ACCELERATION SWEEP ANALYSIS")
    print("="*70)
    print(f"Belt: {belt_name}")
    print()
    
    # Find all improved sweep files
    pattern = f"/tmp/adxl345-improved_sweep_{belt}_*.csv"
    files = sorted(glob.glob(pattern))
    
    if not files:
        print(f"✗ No improved sweep data found!")
        print(f"  Looking for: {pattern}")
        print()
        print("Run the improved sweep test first:")
        print(f"  python3 acceleration_sweep_improved.py {belt}")
        return
    
    print(f"Found {len(files)} test files")
    print()
    print("="*70)
    
    results = []
    
    for filepath in files:
        # Extract acceleration from filename
        import os
        filename = os.path.basename(filepath)
        # Format: adxl345-improved_sweep_a_1000.csv
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
    print("Accel     Frequency   Q-Factor   SNR    Decay  Score  Confidence")
    print("-"*70)
    
    best_score = 0
    best_accel = None
    high_confidence_results = []
    
    for r in results:
        accel = r['acceleration']
        freq = r['frequency']
        q = r['q_factor']
        snr = r['snr']
        score = r['score']
        conf = r['confidence']
        
        # Check if best candidate has decay
        decay_str = "?"
        if 'all_candidates' in r and len(r['all_candidates']) > 0:
            best_candidate = r['all_candidates'][0]
            if best_candidate.get('is_decaying', False):
                decay_str = "✓"
            else:
                decay_str = "✗"
        
        marker = ""
        if score > best_score:
            best_score = score
            best_accel = accel
            marker = " ⭐"
        
        if conf in ['HIGH', 'MEDIUM']:
            high_confidence_results.append(r)
        
        print(f"{accel:5d}     {freq:6.1f} Hz   Q={q:5.1f}   {snr:4.1f}x   {decay_str}     {score:2d}/10  {conf:6s}{marker}")
    
    print()
    print("="*70)
    
    if high_confidence_results:
        print(f"✓ SUCCESS! Found {len(high_confidence_results)} high-confidence result(s)!")
        print()
        
        for r in high_confidence_results:
            print(f"Acceleration: {r['acceleration']} mm/s²")
            print(f"  Frequency: {r['frequency']:.1f} Hz")
            print(f"  Q-Factor: {r['q_factor']:.1f} (sharp peak)")
            print(f"  SNR: {r['snr']:.1f}:1")
            print(f"  Confidence: {r['confidence']}")
            print(f"  Score: {r['score']}/10")
            print()
        
        best_result = high_confidence_results[0]
        
        print("="*70)
        print("RECOMMENDED SETTINGS")
        print("="*70)
        print(f"  Acceleration: {best_result['acceleration']} mm/s²")
        print(f"  Belt frequency: {best_result['frequency']:.1f} Hz")
        print(f"  Signal quality: {best_result['confidence']}")
        print()
        print("This acceleration provides:")
        print(f"  ✓ Clean belt resonance signal")
        print(f"  ✓ Proper decay profile")
        print(f"  ✓ Minimal structural noise")
        
    elif best_accel:
        print(f"⚠ PARTIAL SUCCESS")
        print(f"  Best acceleration: {best_accel} mm/s² (score: {best_score}/10)")
        
        best_result = next(r for r in results if r['acceleration'] == best_accel)
        
        print()
        print(f"Detected frequency: {best_result['frequency']:.1f} Hz")
        print(f"Confidence: {best_result['confidence']}")
        print()
        
        if best_score < 4:
            print("Signal quality is still LOW. Possible issues:")
            print("  - Belt tension may be very high (>140 Hz) or very low (<80 Hz)")
            print("  - Structural resonance (176 Hz) dominating signal")
            print("  - Need larger movement (try 30-50mm instead of 20mm)")
    else:
        print("✗ No clear signal detected")
        print()
        print("Next steps:")
        print("  1. Check if 176-177 Hz structural resonance appears consistently")
        print("  2. Try manual pluck detection instead")
        print("  3. Verify belt is properly tensioned (not too loose, not too tight)")
    
    print()
    print("="*70)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_improved_sweep.py <belt>")
        sys.exit(1)
    
    belt = sys.argv[1].lower()
    
    if belt not in ['a', 'b']:
        print("Belt must be 'a' or 'b'")
        sys.exit(1)
    
    analyze_improved_sweep(belt)

if __name__ == "__main__":
    main()
