# Belt Frequency Analysis — Prompt for Gemini

## What We Are Trying to Do

We are building a tool that measures the resonant frequency of the drive belts on a CoreXY 3D printer (Voron 2.4, 350×350 mm) using its built-in ADXL345 accelerometer. The goal is to help the user balance belt tensions precisely.

The printer runs Klipper firmware. We use its `TEST_RESONANCES` command, which commands the toolhead to oscillate at a slowly-increasing frequency (frequency sweep, 85→140 Hz over ~27 seconds) while the accelerometer records acceleration. This is the same sweep used for input shaper tuning, but we are reading it for belt frequency.

---

## CoreXY Belt Physics — Why Frequency Changes with Y Position

In a CoreXY printer, each belt forms a long loop. The part of the belt that vibrates freely is the segment running between the toolhead and the nearest pulley. **This free segment length changes as the toolhead moves in Y.**

A belt under tension vibrates like a guitar string. Its resonant frequency is:

```
f = (1 / 2L) × sqrt(T / μ)
```

Where:
- `L` = free segment length
- `T` = belt tension
- `μ` = belt linear mass density (constant)

**When the toolhead moves in Y:**
- Moving to lower Y (e.g., Y=80): free segment gets **shorter** → frequency goes **up**
- Moving to higher Y (e.g., Y=120): free segment gets **longer** → frequency goes **down**

This is identical to pressing your finger closer to the nut on a guitar string — the shorter the string, the higher the pitch.

**Crucially:** Structural resonances (frame resonances, rod resonances, motor mounts) are fixed in frequency. They do not change when the toolhead moves. The belt resonance DOES shift with Y.

---

## Ground Truth — Guitar Tuner Measurements

Before running the accelerometer scans, we measured each belt frequency manually using a guitar tuner app (touching the physical belt and reading the vibration frequency). We measured at three Y positions:

| Y Position | Belt A (Hz) | Belt B (Hz) | Notes |
|------------|-------------|-------------|-------|
| Y = 80 mm  | 134         | 135         | Short segment, high freq |
| Y = 100 mm | 110         | 110         | Standard measurement point |
| Y = 120 mm |  98         | 101         | Long segment, low freq |

**Observations:**
- Both belts are essentially equal in tension (less than 1 Hz difference at each position)
- The frequency drops ~36 Hz from Y=80 to Y=120 (a 26% drop over 40mm)
- This confirms the physics: the free segment length changes meaningfully with Y

**The accelerometer scan was performed at Y = 100 mm.** So the expected belt frequency in the scan data is **~110 Hz for both belts.**

---

## What the Accelerometer Scan Looks Like

The scan commands the toolhead to oscillate in a specific direction axis (which selectively excites one belt more than the other in CoreXY geometry), sweeping from 85 Hz to 140 Hz over 27.5 seconds at ~2 Hz/sec. The accelerometer records at ~3215 Hz sample rate.

- **Belt A** = top belt, connects to A DRIVE motor. Scan axis `(1, -1)`.
- **Belt B** = bottom belt, connects to B DRIVE motor. Scan axis `(1, +1)`.

Each scan produces a CSV with columns: `timestamp, accel_x, accel_y, accel_z`

---

## Current Algorithm Result (our app)

We ran an FFT-based algorithm on the scan data. The algorithm:
1. Takes the full 27.5s signal
2. Applies a Hanning window
3. Computes a zero-padded FFT
4. Searches 85–140 Hz for the dominant peak

Results:
- **Belt A**: 107.4 Hz (SNR=19.0, HIGH confidence)
- **Belt B**: 104.1 Hz (SNR=34.9, HIGH confidence)

**The problem:** The guitar tuner says both belts are at 110 Hz. Our algorithm reads 107.4 Hz (A) and 104.1 Hz (B). We believe structural resonances in the frame are being mistaken for belt signal.

---

## Full Spectrum Data (85–145 Hz, normalized to 100% = highest peak)

This is the power spectral density at each 1 Hz bin. The scan is performed at Y=100 mm.

### Belt A Scan (expected belt frequency: ~110 Hz)

Top peaks by power:
```
107.4 Hz  100.0%   <- algorithm chose this (WRONG — tuner says 110 Hz)
114.0 Hz   99.9%
102.6 Hz   74.0%
115.7 Hz   72.6%
105.0 Hz   69.6%
113.0 Hz   67.2%
111.9 Hz   57.9%
110.1 Hz   53.7%   <- this is likely the real belt frequency
```

Full 1 Hz resolution table:
```
 Hz    Power%    Hz    Power%    Hz    Power%
 85.0   13.35   105.0   39.04   125.0    3.31
 86.0    2.94   106.0   24.99   126.0    0.44
 87.0    3.63   107.0    3.14   127.0   13.16
 88.0    7.95   108.0   11.00   128.0    3.04
 89.0    2.96   109.0   28.10   129.0    4.10
 90.0    3.70   110.0    8.12   130.0    5.79
 91.0   13.88   111.0    5.16   131.0    3.52
 92.0    1.54   112.0    4.82   132.0    1.62
 93.0    6.31   113.0   59.90   133.0   12.43
 94.0    6.20   114.0   77.60   134.0    3.51
 95.0    0.65   115.0    8.44   135.0    2.81
 96.0    3.15   116.0   20.98   136.0    0.37
 97.0    4.24   117.0   29.02   137.0    0.07
 98.0    4.64   118.0    1.91   138.0    6.67
 99.0   23.71   119.0   11.30   139.0    1.39
100.0    3.76   120.0    2.11   140.0    2.62
101.0    4.50   121.0    2.75   141.0    1.50
102.0    0.68   122.0    3.07   142.0    4.50
103.0   13.01   123.0    0.71   143.0    0.01
104.0   23.31   124.0   18.76   144.0    1.04
                                145.0    1.83
```

### Belt B Scan (expected belt frequency: ~110 Hz)

Top peaks by power:
```
104.1 Hz  100.0%   <- algorithm chose this (WRONG — tuner says 110 Hz)
106.9 Hz   77.8%
108.9 Hz   77.7%
105.1 Hz   61.9%
113.7 Hz   51.9%
109.0 Hz   44.8%
```

Full 1 Hz resolution table:
```
 Hz    Power%    Hz    Power%    Hz    Power%
 85.0    0.50   105.0   14.06   125.0    2.71
 86.0    9.51   106.0    2.86   126.0    0.47
 87.0    1.99   107.0    2.68   127.0    1.34
 88.0    0.90   108.0   27.17   128.0    0.65
 89.0    0.56   109.0   44.78   129.0    0.42
 90.0    0.86   110.0    1.22   130.0    1.91
 91.0   20.77   111.0   16.15   131.0    4.80
 92.0    0.29   112.0    2.85   132.0    2.39
 93.0    6.39   113.0    8.75   133.0    0.48
 94.0    3.40   114.0    0.10   134.0    0.30
 95.0    1.22   115.0   35.77   135.0    1.16
 96.0   12.37   116.0    0.04   136.0    0.31
 97.0    3.91   117.0    1.11   137.0    0.60
 98.0    8.00   118.0    0.66   138.0    0.25
 99.0    5.87   119.0    6.23   139.0    0.92
100.0    0.88   120.0    0.21   140.0    2.59
101.0    1.40   121.0    0.60   141.0    0.67
102.0   16.63   122.0    6.34   142.0    0.03
103.0   12.73   123.0    0.63   143.0    0.16
104.0    1.42   124.0    2.44   144.0    0.01
                                145.0    1.06
```

---

## Questions for Gemini

We want your help with three things:

### 1. Identify the belt signal in the spectrum

Given that the guitar tuner says both belts are at **110 Hz** at Y=100mm, look at the spectrum data above.

- **For Belt A:** Is 110.1 Hz (53.7%) the real belt signal being masked by structural resonances? What are the other large peaks (107.4, 113–114 Hz cluster) likely to be?
- **For Belt B:** 110 Hz shows only 1.22% power — where did the belt signal go? Is the belt signal somewhere else in this spectrum and we are misidentifying it?

### 2. Explain the position-sweep approach

We are considering a new measurement technique: instead of holding position and sweeping frequency, we would hold a fixed drive frequency and sweep the toolhead Y position (e.g., move slowly from Y=80 to Y=120 while vibrating at a fixed frequency).

At the resonant frequency, when the toolhead passes the Y position where the belt length creates a resonance, we should see a peak in accelerometer output.

**How would you design this approach?**
- What frequency to drive at?
- How to extract the belt frequency from this data?
- Why would this better reject structural resonances compared to the current method?

### 3. Algorithm improvement

Given all the evidence above, what specific changes to our FFT-based algorithm would help it correctly identify 110 Hz instead of 104–107 Hz?

Please show your reasoning step by step, and explain exactly how you arrived at each conclusion.

---

## Additional Context

- Printer: Voron 2.4, 350×350mm, CoreXY kinematics
- Belt: Gates 2GT, 6mm width
- ADXL345 accelerometer mounted on toolhead
- Sweep: 85–140 Hz at 2 Hz/sec (27.5 seconds total)
- Sample rate: ~3215 Hz
- Measurement Y position: Y=100mm (toolhead at probe point 175, 100, 20)
- Free belt segment at Y=100: ~150mm (community standard measurement length)
