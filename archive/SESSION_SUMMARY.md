# Belt Tuner V3 Development Session - Summary

**Date:** February 18, 2026  
**Focus:** V3 Analyzer Development & Git Organization Prep

---

## Current Status

### ✅ Completed
1. **V3 Analyzer Created** - `belt_analyzer_v3.py`
   - Peak-to-Decay triggering (margin protection against electrical spikes)
   - Notch filter at 176Hz (removes structural resonance)
   - Tight bandpass (90-140Hz)
   - Welch PSD for noise immunity
   - Zero-padded FFT (8192) for sub-Hz precision
   - Parabolic interpolation

2. **KlipperScreen Panel Updated** - `belt_tuner_panel.py`
   - Now imports V3 analyzer
   - Quality-based confidence labels (HIGH/MEDIUM/LOW)
   - Removed blocking on low-quality measurements
   - Reduced spacing for small screens
   - Auto CSV cleanup (keeps last 10 files)

3. **Macros Updated**
   - `belt_tuner_macros.cfg` - references V3
   - `belt_tuner_macros_simple.cfg` - references V3

4. **Installation Scripts Ready**
   - `install.sh` - Git-based one-command installer
   - `uninstall.sh` - Clean removal

### ⚠️ Known Issues

**Frequency Discrepancy (~5Hz gap)**
- Your results: Belt A = 114.2/114.8/114.5 Hz, Belt B = 111.4/112.1/111.8 Hz
- My results from uploaded files: Belt A = 109 Hz, Belt B varies wildly
- **Hypothesis:** Files uploaded may not be the same ones you tested locally
- **Next step:** Test V3 on fresh Pi install, upload raw CSV files for comparison

**Workaround Applied:**
- Added `analyze_pluck_v3 = analyze_pluck_event` alias to V3 file on printer

---

## Project File Structure (Current)

### On Your Printer (`~/Live-Belt-Tension/`)
```
Live-Belt-Tension/
├── src/
│   ├── belt_tuner.py
│   ├── belt_analyzer_v2.py
│   ├── belt_analyzer_v3.py  ← NEW (needs full version copied)
│   ├── belt_calibration.py
│   └── belt_tuner_panel.py  ← UPDATED
├── config/
│   ├── belt_tuner_macros.cfg  ← UPDATED
│   └── belt_tuner.css
└── extras/
    └── gcode_shell_command.py
```

### Files You Have Ready (from outputs/)
- `belt_analyzer_v3.py` - Latest version with all improvements
- `belt_tuner_panel.py` - Updated to use V3
- `belt_tuner_macros.cfg` - Updated paths
- `belt_tuner_macros_simple.cfg` - Updated paths
- `install.sh` - Git installer
- `uninstall.sh` - Removal script

---

## Recommended Git Organization

```
Live-Belt-Tension/
├── README.md                    # Main project docs
├── LICENSE                      # MIT or GPL
├── install.sh                   # One-command installer
├── uninstall.sh                 # Clean removal
│
├── src/                         # Python source files
│   ├── belt_tuner.py           # Main macro handler
│   ├── belt_analyzer_v3.py     # Signal processing (production)
│   ├── belt_calibration.py     # Calibration logic
│   └── belt_tuner_panel.py     # KlipperScreen UI
│
├── config/                      # Klipper configs
│   ├── belt_tuner_macros.cfg   # Full feature set
│   ├── belt_tuner_macros_simple.cfg  # Minimal version
│   └── belt_tuner.css          # KlipperScreen styling
│
├── extras/                      # Klipper extensions
│   └── gcode_shell_command.py  # Shell command support
│
├── docs/                        # Documentation
│   ├── INSTALL.md              # Installation guide
│   ├── USAGE.md                # How to use
│   ├── TROUBLESHOOTING.md      # Common issues
│   ├── TECHNICAL.md            # Signal processing details
│   └── CHANGELOG.md            # Version history
│
├── archive/                     # Old versions (optional)
│   ├── belt_analyzer_v2.py     # Previous version
│   └── old_macros/
│
└── examples/                    # Sample data (optional)
    └── sample_measurements/
```

---

## Next Steps for Git Setup

### 1. Initialize Repository
```bash
cd ~/Live-Belt-Tension
git init
```

### 2. Create `.gitignore`
```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*.so
*.egg-info/
.Python

# CSV data files
*.csv
/tmp/

# OS files
.DS_Store
Thumbs.db

# Editor files
*.swp
*.swo
*~
.vscode/
.idea/

# Test files
test_*.py
debug_*.log
EOF
```

### 3. Organize Files
```bash
# Move everything to proper locations
mkdir -p src config extras docs archive

# Move current files (adjust paths as needed)
mv belt_tuner.py src/
mv belt_analyzer_v3.py src/
mv belt_calibration.py src/
mv belt_tuner_panel.py src/

mv belt_tuner_macros.cfg config/
mv belt_tuner.css config/

mv gcode_shell_command.py extras/

# Archive old versions
mv belt_analyzer_v2.py archive/
```

### 4. Create README.md
See next section for template.

### 5. First Commit
```bash
git add .
git commit -m "Initial commit - Belt Tuner V3 with live frequency analysis"
```

### 6. Create GitHub Repo
```bash
# On GitHub, create new repo (don't initialize with README)
# Then:
git remote add origin https://github.com/YOUR_USERNAME/Live-Belt-Tension.git
git branch -M main
git push -u origin main
```

---

## README.md Template

```markdown
# Live Belt Tension Analyzer

Real-time belt frequency analysis for CoreXY 3D printers using ADXL345 accelerometer.

## Features

- **Manual Pluck Detection** - Trigger analysis by physically plucking the belt
- **Sub-Hz Precision** - Zero-padded FFT with parabolic interpolation
- **Noise Immunity** - Welch PSD averaging for consistent results
- **KlipperScreen UI** - Touch-friendly interface with live comparison
- **Auto Cleanup** - Manages CSV files automatically

## Quick Install

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/Live-Belt-Tension.git
cd Live-Belt-Tension
chmod +x install.sh
./install.sh
```

## Requirements

- Klipper firmware
- KlipperScreen
- ADXL345 accelerometer configured
- Python 3.7+ with numpy, scipy, pandas

## Usage

### Via KlipperScreen
1. Navigate to Belt Tuner panel
2. Click "Measure Belt A" or "Measure Belt B"
3. Physically pluck the belt when prompted
4. View results and comparison

### Via G-code
```gcode
BELT_TUNER_MEASURE BELT=A
BELT_TUNER_MEASURE BELT=B
BELT_TUNER_COMPARE
```

### Manual Analysis
```bash
python3 ~/Live-Belt-Tension/src/belt_analyzer_v3.py /tmp/adxl345-belt_A.csv
```

## How It Works

1. **Trigger Detection** - Finds the peak acceleration (the "snap")
2. **Window Extraction** - Analyzes 1s of decay starting 50ms after impact
3. **Filtering** - Notch at 176Hz + bandpass 90-140Hz
4. **Frequency Analysis** - Welch PSD + zero-padded FFT
5. **Sub-Hz Precision** - Parabolic interpolation of peak

## Troubleshooting

**"Insufficient data after trigger"**
- Recording too short - increase ACCEL_CHIP_DURATION in macros

**Low Q-factor / LOW confidence**
- Pluck harder
- Check ADXL mounting (should be rigid)
- Ensure belt is accessible for clean pluck

**Results inconsistent**
- Use same pluck location each time
- Position toolhead at bed center
- Avoid touching frame during measurement

## Technical Details

- Sample rate: ~3200 Hz
- Analysis window: 1 second (post-trigger)
- Frequency range: 90-140 Hz (typical CoreXY belt range)
- Expected results: 100-120 Hz depending on tension

## Contributing

Pull requests welcome! Please test on hardware before submitting.

## License

MIT License - see LICENSE file

## Credits

Inspired by manual belt frequency apps and the Klipper community.
```

---

## Technical Details Reference

### V3 Analyzer Pipeline

1. **Load CSV** - pandas with `comment='#'`
2. **DC Removal** - Per-axis before magnitude calculation
3. **Magnitude** - `sqrt(x² + y² + z²)` includes Z-axis
4. **Peak Trigger** - `argmax(abs(signal[margin:-margin]))` with 100-sample margins
5. **Window** - 50ms skip + 1000ms analysis window
6. **Notch Filter** - 176Hz Q=30 (structural resonance removal)
7. **Bandpass** - 90-140Hz 4th order Butterworth
8. **Welch PSD** - `nperseg=fs/2` for noise averaging
9. **Zero-Pad FFT** - n=8192 with Hanning window
10. **Peak Search** - Find max in 90-140Hz mask
11. **Parabolic Interp** - `delta = 0.5*(left-right)/(left-2*mid+right)`
12. **Q-Factor** - `freq / bandwidth_at_half_power`

### Key Improvements Over V2

| Feature | V2 | V3 |
|---------|----|----|
| Trigger | Rolling variance | Absolute peak with margins |
| Z-axis | Ignored | Included in magnitude |
| Filtering | Single bandpass | Notch + bandpass |
| Frequency | Single FFT | Welch PSD + FFT |
| Padding | Minimal | 8192 zero-pad |
| Noise immunity | Low | High (Welch averaging) |

---

## Files Reference

### Core Files (Required)
- `belt_analyzer_v3.py` - Signal processing engine
- `belt_tuner.py` - Klipper macro handler
- `belt_tuner_macros.cfg` - G-code macros
- `gcode_shell_command.py` - Shell execution support

### UI Files (Optional)
- `belt_tuner_panel.py` - KlipperScreen interface
- `belt_tuner.css` - Panel styling

### Utility Files
- `belt_calibration.py` - Stores last measurements
- `install.sh` - Automated setup
- `uninstall.sh` - Clean removal

---

## Open Questions / TODOs

### Testing Needed
- [ ] Fresh Pi install validation
- [ ] Compare V3 output to manual app with identical CSV files
- [ ] Test on multiple printer configurations
- [ ] Verify cleanup works over time

### Documentation
- [ ] Add wiring diagrams for ADXL345
- [ ] Screenshot KlipperScreen panel
- [ ] Video demonstration
- [ ] Frequency range guide by printer size

### Future Enhancements
- [ ] Auto-compare after both belts measured
- [ ] Historical tracking (CSV log of measurements)
- [ ] Tension recommendations based on frequency
- [ ] Integration with resonance testing
- [ ] Support for other accelerometers

---

## Commands Quick Reference

### On Printer
```bash
# Copy new V3 analyzer
cp belt_analyzer_v3.py ~/Live-Belt-Tension/src/

# Copy updated panel
cp belt_tuner_panel.py ~/KlipperScreen/panels/

# Restart KlipperScreen
sudo systemctl restart KlipperScreen

# Test analyzer directly
python3 ~/Live-Belt-Tension/src/belt_analyzer_v3.py /tmp/test.csv

# Check which version is loaded
python3 -c "from belt_analyzer_v3 import analyze_pluck_v3; print('OK')"
```

### Git Commands
```bash
# Status
git status

# Stage all changes
git add .

# Commit
git commit -m "Description of changes"

# Push to GitHub
git push origin main

# Pull latest
git pull origin main

# Create branch
git checkout -b feature-name

# View history
git log --oneline --graph
```

---

## Contact / Support

GitHub Issues: [https://github.com/YOUR_USERNAME/Live-Belt-Tension/issues](https://github.com/YOUR_USERNAME/Live-Belt-Tension/issues)

---

**End of Session Summary**
