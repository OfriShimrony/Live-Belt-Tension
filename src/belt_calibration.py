#!/usr/bin/env python3
"""
Belt Frequency Calibration Test
--------------------------------
Records 9 measurements at known frequencies to calibrate the detector.

Test plan:
- 3 measurements at ~115 Hz
- 3 measurements at ~110 Hz  
- 3 measurements at ~105 Hz

This will show us how accurately we can detect known frequencies.
"""

import requests
import time
import sys
import os
from belt_pluck_detector import analyze_pluck, send_gcode, find_latest_csv

def calibration_test(belt_name):
    """Run calibration with 9 measurements"""
    
    print("\n" + "="*70)
    print("BELT FREQUENCY CALIBRATION TEST")
    print("="*70)
    print(f"Belt: {belt_name}")
    print()
    print("Test Plan:")
    print("  - Measurements 1-3: Tune belt to ~115 Hz (tight)")
    print("  - Measurements 4-6: Adjust to ~110 Hz (medium)")
    print("  - Measurements 7-9: Adjust to ~105 Hz (loose)")
    print()
    print("For each measurement:")
    print("  1. Countdown 3-2-1")
    print("  2. PLUCK when you see 'PLUCK NOW!'")
    print("  3. Recording continues 3 more seconds after pluck")
    print("  4. Manual tuner app reading will be requested")
    print()
    print("="*70)
    print()
    
    input("Press ENTER to start calibration...")
    
    results = []
    
    for test_num in range(1, 10):
        print("\n" + "-"*70)
        print(f"MEASUREMENT {test_num}/9")
        print("-"*70)
        
        # Instructions for this group
        if test_num == 1:
            print("→ Tune belt to ~115 Hz (tight) and take 3 measurements")
        elif test_num == 4:
            print("→ Adjust belt to ~110 Hz (medium) and take 3 measurements")
        elif test_num == 7:
            print("→ Adjust belt to ~105 Hz (loose) and take 3 measurements")
        
        print()
        input(f"  Press ENTER when ready for measurement {test_num}...")
        
        # Start measurement
        send_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
        time.sleep(0.3)
        
        # Countdown
        print()
        print("  Pluck in:")
        for i in range(3, 0, -1):
            print(f"    {i}...")
            time.sleep(0.8)
        
        print("    >>> PLUCK NOW! <<<")
        print()
        print("  Recording for 3 more seconds...")
        
        # Continue recording for 3 seconds after pluck
        time.sleep(3.0)
        
        # Stop measurement
        send_gcode(f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME=calibration_{belt_name}_{test_num}")
        time.sleep(0.5)
        
        # Get manual reading
        print()
        manual_freq = input("  Enter manual tuner app reading (Hz): ").strip()
        
        try:
            manual_freq = float(manual_freq)
        except:
            print("  Warning: Invalid frequency, using 0")
            manual_freq = 0
        
        # Analyze
        print("  Analyzing...")
        csv_file = find_latest_csv()
        
        if csv_file:
            result = analyze_pluck(csv_file, belt_name)
            
            if 'error' not in result:
                auto_freq = result['frequency']
                confidence = result['confidence']
                q_factor = result['q_factor']
                score = result['score']
                
                error = auto_freq - manual_freq if manual_freq > 0 else 0
                
                print()
                print(f"  Manual:    {manual_freq:.1f} Hz")
                print(f"  Automated: {auto_freq:.1f} Hz ({confidence} confidence)")
                print(f"  Error:     {error:+.1f} Hz")
                print(f"  Q-Factor:  {q_factor:.1f}")
                print(f"  Score:     {score}/10")
                
                results.append({
                    'test_num': test_num,
                    'manual': manual_freq,
                    'automated': auto_freq,
                    'error': error,
                    'confidence': confidence,
                    'q_factor': q_factor,
                    'score': score,
                    'all_candidates': result.get('all_candidates', [])
                })
            else:
                print(f"  ✗ Analysis error: {result['error']}")
                results.append({
                    'test_num': test_num,
                    'manual': manual_freq,
                    'error_msg': result['error']
                })
        else:
            print("  ✗ No data file found")
            results.append({
                'test_num': test_num,
                'manual': manual_freq,
                'error_msg': 'No data file'
            })
    
    # Summary report
    print("\n\n" + "="*70)
    print("CALIBRATION SUMMARY")
    print("="*70)
    print()
    print("Test  Manual   Automated  Error   Confidence  Q-Factor  Score")
    print("-"*70)
    
    valid_results = [r for r in results if 'automated' in r]
    
    for r in results:
        if 'automated' in r:
            print(f" {r['test_num']:2d}   {r['manual']:6.1f}   {r['automated']:9.1f}  {r['error']:+6.1f}  {r['confidence']:10s}  {r['q_factor']:8.1f}  {r['score']:2d}/10")
        else:
            print(f" {r['test_num']:2d}   {r['manual']:6.1f}   ERROR: {r.get('error_msg', 'Unknown')}")
    
    print()
    print("="*70)
    
    if valid_results:
        errors = [abs(r['error']) for r in valid_results if r['manual'] > 0]
        
        if errors:
            print()
            print("ACCURACY STATISTICS:")
            print(f"  Mean absolute error: {sum(errors)/len(errors):.1f} Hz")
            print(f"  Max error: {max(errors):.1f} Hz")
            print(f"  Min error: {min(errors):.1f} Hz")
            print()
            
            # Group by target frequency
            group_115 = [r for r in valid_results if 1 <= r['test_num'] <= 3 and r['manual'] > 0]
            group_110 = [r for r in valid_results if 4 <= r['test_num'] <= 6 and r['manual'] > 0]
            group_105 = [r for r in valid_results if 7 <= r['test_num'] <= 9 and r['manual'] > 0]
            
            for group_name, group in [("~115 Hz", group_115), ("~110 Hz", group_110), ("~105 Hz", group_105)]:
                if group:
                    avg_error = sum(abs(r['error']) for r in group) / len(group)
                    avg_auto = sum(r['automated'] for r in group) / len(group)
                    avg_manual = sum(r['manual'] for r in group) / len(group)
                    print(f"  {group_name}: Manual avg={avg_manual:.1f} Hz, Auto avg={avg_auto:.1f} Hz, Error={avg_error:.1f} Hz")
            
            print()
            
            # Check if we need calibration offset
            avg_error_signed = sum(r['error'] for r in valid_results if r['manual'] > 0) / len([r for r in valid_results if r['manual'] > 0])
            print(f"  Average signed error: {avg_error_signed:+.1f} Hz")
            if abs(avg_error_signed) > 3:
                print(f"  → Recommendation: Apply calibration offset of {-avg_error_signed:.1f} Hz")
            else:
                print(f"  → No calibration offset needed (error < 3 Hz)")
    
    print()
    print("="*70)
    print("Calibration complete!")
    print()
    
    # Show top 5 candidates for each test to see if correct frequency appears
    print("\n" + "="*70)
    print("DETAILED CANDIDATE ANALYSIS")
    print("="*70)
    print("(Checking if correct frequency appears in top 5 candidates)")
    print()
    
    for r in valid_results:
        if r['manual'] > 0 and 'all_candidates' in r:
            print(f"Test {r['test_num']}: Manual={r['manual']:.1f} Hz")
            print(f"  Top 5 detected frequencies:")
            for i, cand in enumerate(r['all_candidates'][:5], 1):
                error = cand['freq'] - r['manual']
                marker = " ← CLOSEST" if abs(error) < 5 else ""
                print(f"    {i}. {cand['freq']:6.1f} Hz (Q={cand['q_factor']:5.1f}, Score={cand['score']:2d}/10, Error={error:+.1f} Hz){marker}")
            print()
    
    print("="*70)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 belt_calibration.py <belt>")
        print()
        print("Example:")
        print("  python3 belt_calibration.py A")
        sys.exit(1)
    
    belt = sys.argv[1].upper()
    
    if belt not in ['A', 'B']:
        print("Belt must be 'A' or 'B'")
        sys.exit(1)
    
    calibration_test(belt)

if __name__ == "__main__":
    main()
