# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow Instructions

**Before committing any code change, always ask:**
> "Do you want to test this on the printer before committing?"

SSH access to the printer is available via `plink` (PuTTY):
- Host: `10.0.0.24`, user: `pi`
- KlipperScreen panel lives at `~/KlipperScreen/panels/belt_tuner_panel.py`
- After deploying: `sudo systemctl restart KlipperScreen`

---

## Project Overview

**Live Belt Tension** is a real-time belt frequency measurement tool for Klipper-based CoreXY 3D printers. It uses an ADXL345 accelerometer to analyze belt resonant frequency via FFT when the belt is physically plucked, like a guitar tuner.

The project runs **on a Raspberry Pi** (or similar SBC) alongside Klipper, not on this Windows development machine. Files are edited here and deployed to the printer manually or via `git pull`.

## Repository Structure

```
gcode/               # Klipper G-code macro configs (.cfg)
src/                 # Python source files
  belt_analyzer_v3.py   # Signal processing engine (PRODUCTION - use this)
  belt_tuner.py         # Klipper macro handler (talks to Moonraker API)
  belt_tuner_panel.py   # KlipperScreen GTK3 UI panel
  belt_calibration.py   # 9-measurement calibration harness
  belt_analyzer_v2.py   # Old version (superseded by V3)
  belt_tuner_web_ab.py  # Web interface variant
  test/              # Development/experimental scripts (not production)
tests/               # Raw CSV data from ADXL345 for testing analyzers
docs/                # Documentation and research notes
```

## Key Architecture

### Signal Processing Pipeline (V3 — `belt_analyzer_v3.py`)

The main entry point is `analyze_pluck_event(filepath, belt_name, debug=False)`. It returns a dict with `frequency`, `q_factor`, `confidence`, `trigger_time`, `psd_estimate`, `sample_rate`, or `error`.

Pipeline stages:
1. Load CSV (time, accel_x, accel_y columns; `#` comment lines skipped)
2. DC removal per axis, then compute 2D magnitude (`sqrt(x²+y²)`)
3. **Max-peak trigger** — `argmax(abs(magnitude))` finds the pluck moment
4. Extract window: skip 50ms after peak, then 1000ms of decay
5. **Notch filter** at 176Hz Q=30 (structural resonance)
6. **Bandpass** 90–140Hz, 4th-order Butterworth
7. **Welch PSD** (nperseg=fs/4, 50% overlap) for initial frequency estimate
8. **Zero-padded FFT** (n=8192, Hanning window) for smooth spectrum
9. Peak search ±5Hz around PSD estimate
10. **Parabolic interpolation** for sub-Hz precision
11. Q-factor → confidence: EXCELLENT(>50) / HIGH(>20) / GOOD(>10) / LOW

### Component Interactions

- **G-code macros** (`gcode/*.cfg`) define Klipper commands (`BELT_TUNE`, `BELT_COMPARE`)
- Macros call `RUN_SHELL_COMMAND` → `belt_tuner.py` via `gcode_shell_command.py` (Klipper extra)
- `belt_tuner.py` talks to Klipper via **Moonraker REST API** (`http://localhost:7125`)
- It sends `ACCELEROMETER_MEASURE` G-codes, waits, then reads the CSV from `/tmp/adxl345-*.csv`
- `belt_tuner_panel.py` is a **KlipperScreen panel** (GTK3, inherits `ScreenPanel`)
  - Uses background thread + `GLib.idle_add()` for non-blocking UI updates
  - Imports `belt_analyzer_v3.py` directly; searches common Pi home dirs for the file
  - `analyze_pluck_v3` is the expected import alias (same as `analyze_pluck_event`)

### CSV Format

ADXL output from Klipper: `#timestamp,accel_x,accel_y,accel_z` (header row, `#` comments at top)
Sample rate: ~3200 Hz. Minimum useful length: 1000 samples.

### Belt Frequency Range

Expected: 90–140Hz for typical CoreXY printers. Target delta between A and B belts:
- < 2Hz: EXCELLENT
- < 5Hz: GOOD
- < 10Hz: FAIR
- ≥ 10Hz: POOR

## Running the Analyzer

On the printer (Linux):
```bash
# Analyze a CSV directly
python3 ~/Live-Belt-Tension/src/belt_analyzer_v3.py /tmp/adxl345-belt_A.csv

# After measurement via G-code, the CSV lands in /tmp/
```

The analyzer can also be run standalone on this Windows machine for development:
```bash
python src/belt_analyzer_v3.py tests/adxl345-belt_A_1.csv
```

## Dependencies

Python: `numpy`, `scipy` (signal processing), `pandas` (not used in V3, was in V2), `requests` (belt_tuner.py → Moonraker)
KlipperScreen panel additionally needs: `gi` (PyGObject/GTK3), Klipper `ks_includes`

## Deployment

Files deploy to the printer at `~/Live-Belt-Tension/`. The KlipperScreen panel goes to `~/KlipperScreen/panels/belt_tuner_panel.py`.

After updating files on the printer:
```bash
sudo systemctl restart KlipperScreen   # for panel changes
sudo systemctl restart klipper         # for macro changes (after editing .cfg)
```

## Active Issues

**~5Hz frequency discrepancy** — V3 reports different frequencies than manual tuner apps in some tests. Suspected cause: test CSV files may not match what was tested live. Next step: upload raw CSV and compare output to a manual guitar tuner app on the same file.

**`analyze_pluck_v3` alias** — `belt_tuner_panel.py` imports `analyze_pluck_v3` from `belt_analyzer_v3`, but V3 only defines `analyze_pluck_event`. A workaround alias `analyze_pluck_v3 = analyze_pluck_event` was added to the printer's copy. Ensure the repo version includes this alias.

## Files to Ignore / Archive

`src/test/` contains exploratory scripts from early development (streaming, variance-based triggers, web interfaces). These are not used in production.

`src/belt_analyzer_v2.py` is superseded by V3. Keep for reference but don't modify.

`gcode/belt_tune_macros.cfg` and `gcode/belt_measure_macros.cfg` are older macro variants; `belt_tuner_macros.cfg` and `belt_tuner_macros_simple.cfg` are current.
