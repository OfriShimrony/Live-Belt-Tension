# Live Belt Tension Tuner for Klipper

Belt frequency measurement tool for CoreXY 3D printers. Works like a guitar tuner — physically pluck your belt, get the frequency instantly. Uses the ADXL345 accelerometer already on your printer.

## Installation

SSH into your printer and run:

```bash
wget -O - https://raw.githubusercontent.com/OfriShimrony/Live-Belt-Tension/main/install.sh | bash
```

Then add to your `printer.cfg`:

```ini
[include belt_tuner_macros_simple.cfg]
```

And restart Klipper:

```bash
sudo systemctl restart klipper
```

## Requirements

- Klipper with Moonraker
- ADXL345 accelerometer configured for input shaping
- Python 3 with `numpy` and `scipy` (installed automatically)

## Usage

From the Klipper console (Mainsail / Fluidd):

```
BELT_TUNE BELT=A       # Measure Belt A (3 plucks, averaged)
BELT_TUNE BELT=B       # Measure Belt B
BELT_COMPARE           # Measure and compare both belts
```

When prompted, pluck the belt like a guitar string. The tool detects the snap automatically and reports the frequency.

### KlipperScreen Panel (optional)

If you have KlipperScreen, the installer will add a touch-friendly panel automatically. Add it to your KlipperScreen config:

```ini
[menu __main belt_tuner]
name: Belt Tuner
panel: belt_tuner_panel
```

Then restart KlipperScreen:

```bash
sudo systemctl restart KlipperScreen
```

## How It Works

1. The ADXL345 records acceleration data while you pluck the belt
2. The analyzer finds the peak impact and extracts 1 second of decay
3. A notch filter removes the 176 Hz structural resonance
4. Welch PSD + zero-padded FFT with parabolic interpolation gives sub-Hz accuracy
5. Results are reported with a confidence rating (EXCELLENT / HIGH / GOOD / LOW)

**Target frequencies** for a well-tuned CoreXY:
- Belt A vs Belt B delta < 2 Hz: EXCELLENT
- < 5 Hz: GOOD
- < 10 Hz: FAIR
- ≥ 10 Hz: POOR — adjust tension

## Troubleshooting

**"Insufficient data after trigger"** — Recording too short. Check `timeout` in the macro's `gcode_shell_command`.

**LOW confidence** — Pluck harder, or check that the ADXL345 is rigidly mounted.

**Inconsistent results** — Always pluck at the same location. Position the toolhead at bed center before measuring.

## License

MIT

## Author

Ofri Shimrony — inspired by the Klipper community and Prusa's belt tension feature.
