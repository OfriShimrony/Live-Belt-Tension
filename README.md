# Live Belt Tension Tuner for Klipper

A real-time belt tension measurement tool for Klipper-based 3D printers that provides live feedback during belt adjustment.

## Overview

This project aims to create a live belt tension tuner that works like a guitar tuner - providing continuous, real-time frequency feedback as you physically adjust your printer's belt tensioners. Unlike existing solutions that require iterative test-adjust-retest cycles, this tool will show you the belt frequency in real-time.

## Features (Planned)

- **Real-time frequency display**: See belt resonant frequency update live as you adjust
- **Visual target zones**: Clear indication of proper tension ranges
- **A/B belt comparison**: For CoreXY systems, compare both belts simultaneously
- **Web interface**: Integration with Mainsail/Fluidd
- **Multi-printer support**: Tested on Voron V0, V2.4, and Trident

## How It Works

The tool extends Klipper's existing ADXL345 accelerometer support to provide continuous streaming of vibration data. Real-time FFT (Fast Fourier Transform) analysis extracts the dominant frequency, which corresponds to belt tension.

## Project Status

🚧 **Early Development** - Currently in Phase 1: Research & Design

## Requirements

- Klipper-based 3D printer (CoreXY, Cartesian, or Delta)
- ADXL345 accelerometer (already installed for input shaping)
- Raspberry Pi or similar host running Klipper
- Python 3 with NumPy/SciPy

## Development Roadmap

### Phase 1: Research & Design (Current)
- Study Klipper's ADXL345 implementation
- Design system architecture
- Create technical specification

### Phase 2: Prototype Data Collection
- Extend Klipper's adxl345.py module for streaming mode
- Implement Python-side buffer management

### Phase 3: FFT Processing Engine
- Real-time frequency analysis
- Peak detection and noise filtering

### Phase 4: User Interface
- Web-based display with live updates
- Visual frequency indicators

### Phase 5: Testing & Validation
- Test across multiple printer configurations
- Refine and optimize

### Phase 6: Documentation & Release
- Complete user documentation
- Community release

## Contributing

This project is in early development. Contributions, suggestions, and testing help will be welcome once we reach a more stable state.

## License

TBD

## Author

Ofri Shimrony

## Inspiration

This project was inspired by the Klipper community's long-standing desire for live belt tension monitoring (discussed since 2022) and Prusa's recent belt tension feature.

---

*Last updated: February 2026*
