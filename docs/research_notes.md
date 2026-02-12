# Research Notes: Klipper ADXL345 Implementation

## Objective
Understand how Klipper currently handles ADXL345 accelerometer data collection to determine how we can extend it for continuous streaming.

## Key Questions to Answer
1. How does Klipper communicate with the ADXL345?
2. What is the current data flow from accelerometer to host?
3. How does the existing TEST_RESONANCES command work?
4. What buffer mechanisms are already in place?
5. Where would we add our streaming mode?

## File Locations in Klipper Source
- `klippy/extras/adxl345.py` - Main Python module for ADXL345 support
- `klippy/extras/resonance_tester.py` - Handles resonance testing commands
- Microcontroller code (if needed) - in `src/` directory

## Next Steps
1. Clone or download Klipper source code
2. Read through `klippy/extras/adxl345.py`
3. Document key functions and data structures
4. Identify where to add streaming capability

---

## Notes Section (to be filled in as we research)

### adxl345.py Structure

*(We'll add notes here as we examine the code)*

### Current Data Collection Flow

*(We'll diagram this as we understand it)*

### Opportunities for Extension

*(We'll identify where our code will plug in)*
