# Auto-Direction Branch — Snapshot Summary

**Snapshot date:** 2026-02-26
**Branched from:** `debug` at commit `5597c3c`

---

## What's in this branch

This branch captures the work-in-progress (WIP) state of an **automated belt frequency detection system** that does NOT require the user to manually pluck the belt. Instead, it moves the toolhead while recording ADXL accelerometer data and extracts belt frequencies from the resulting spectrum.

### Files changed vs last commit

| File | What changed |
|------|-------------|
| `src/belt_sweep_analyzer.py` | New `analyze_multi_position_sweep()` — sweeps motion data at multiple positions, identifies the mobile frequency peak (belt) vs fixed structural resonances |
| `src/belt_tuner_moonraker.py` | New `/server/belt_tuner/motion_measure_dynamic` endpoint — moves toolhead to 3 positions (125,125 / 175,175 / 225,225), records ADXL at each, analyzes |
| `src/belt_tuner_panel.py` | "Dyn A" / "Dyn B" buttons in scan mode (scan_row2) — triggers dynamic scan, polls progress every 5 s, displays result |
| `CLAUDE.md` | Next task notes, calibration update for Belt A |

---

## Research findings (why this direction was paused)

From `tests/` data (diagonal sweeps, imbalance tests):

- ADXL is **dominated by structural resonance at ~121 Hz** — fixed, doesn't move with position or belt tension
- Secondary peak at ~80–83 Hz is position-sensitive but **NOT belt-specific** (loosening Belt A affects Belt B equally)
- Response is **global** — individual belts cannot be isolated this way
- At extreme position (225,225): balanced belts → ~85 Hz dominant; imbalanced → flips to 121 Hz

**Conclusion:** The motion-based approach cannot reliably distinguish which belt is contributing to which peak. The pluck-based approach (belt_analyzer_v3.py) is more reliable.

---

## Multi-position dynamic scan — how it works

1. Moonraker component accepts POST `/server/belt_tuner/motion_measure_dynamic` with `{"belt": "A"|"B"}`
2. Moves toolhead to 3 diagonal positions along the belt's axis
3. At each position: records a frequency sweep (ADXL resonance test) via Klipper
4. `analyze_multi_position_sweep()` computes the **structural fingerprint** (peaks common to all positions) and excludes them
5. The remaining mobile peak is reported as the belt frequency

### Calibration status (as of snapshot)

- `calibration_a` in moonraker.conf is **stale** — Belt A is now at ~104.5 Hz (not the stored 110 Hz at Y=100)
- Multi-position scan reported Belt A = 109.3 Hz (off by 4.8 Hz), Belt B = 108.8 Hz (accurate)
- Root cause: algorithm searches near calibration-expected frequency

---

## Why we switched direction

The user decided to return to the **working pluck-based system** (belt_analyzer_v3.py) and redesign the KlipperScreen panel to support **continuous background recording** ("continuous pluck monitoring mode"), which is strictly better UX than the current manual countdown approach.

See MEMORY.md for full details of the next planned feature.

---

## To resume this direction

1. `git checkout auto-direction`
2. Deploy to printer as per MEMORY.md instructions
3. Address calibration stale issue (re-measure Belt A at Y=80/100/120 with guitar tuner)
4. Investigate klippain-shaketune for comparison approach to isolate individual belt contributions
