"""
Moonraker component for Live Belt Tension.

Deploy to: ~/moonraker/moonraker/components/belt_tuner.py
Activate by adding [belt_tuner] to moonraker.conf.

Exposes:
  POST /server/belt_tuner/measure                {"belt": "A"}
  POST /server/belt_tuner/motion_measure         {"belt": "A", "freq_min": 85, "freq_max": 140}
  POST /server/belt_tuner/motion_measure_dynamic {"belt": "A"}
  GET  /server/belt_tuner/status
  POST /server/belt_tuner/clear                  {"belt": "A"}  (omit belt to clear both)
"""

from __future__ import annotations
import asyncio
import glob
import logging
import os
import sys

from ..common import RequestType

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper
    from ..common import WebRequest
    from .klippy_apis import KlippyAPI

logger = logging.getLogger(__name__)

ANALYZER_SEARCH_PATHS = [
    os.path.expanduser("~/Live-Belt-Tension/src"),
    "/home/pi/Live-Belt-Tension/src",
    "/home/mks/Live-Belt-Tension/src",
    "/home/biqu/Live-Belt-Tension/src",
]

EMPTY_RESULT: Dict[str, Any] = {
    'frequency': None, 'confidence': None, 'q_factor': None, 'error': None
}


class BeltTuner:
    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.klippy_apis: KlippyAPI = self.server.lookup_component('klippy_apis')
        # Probe point for TEST_RESONANCES.
        # Set to the toolhead position where the free belt segment length is ~150mm
        # (the community standard measurement length). On most CoreXY printers this
        # is around Y=100 regardless of bed size, e.g. "175, 100, 20".
        self.probe_point: str = config.get('probe_point', '')
        # Scan axes for Belt A and Belt B.
        # CoreXY belt isolation depends on motor wiring.  On most Voron printers
        # Belt A = 1,1 and Belt B = 1,-1, but some printers are reversed.
        # If the app reports A and B in the wrong order compared to your physical
        # belts, swap these two values.
        self.axis_a: str = config.get('axis_a', '1,1')
        self.axis_b: str = config.get('axis_b', '1,-1')
        # Optional calibration from a guitar tuner (y_position:frequency_hz pairs).
        # Example: calibration_a: 80:134, 100:110, 120:98
        # If provided, the multi-position dynamic scan uses these to identify the
        # belt peak in the spectrum.  Omit to use pure mobility+power scoring.
        self._calibration_a: List[Dict[str, float]] = self._parse_calibration(
            config.get('calibration_a', '')
        )
        self._calibration_b: List[Dict[str, float]] = self._parse_calibration(
            config.get('calibration_b', '')
        )
        self._status: Dict[str, Any] = {
            'A': dict(EMPTY_RESULT),
            'B': dict(EMPTY_RESULT),
        }
        self._measuring = False
        self._measure_lock = asyncio.Lock()
        self._dyn_progress: Optional[str] = None

        self.server.register_endpoint(
            "/server/belt_tuner/measure", RequestType.POST, self._handle_measure
        )
        self.server.register_endpoint(
            "/server/belt_tuner/motion_measure", RequestType.POST, self._handle_motion_measure
        )
        self.server.register_endpoint(
            "/server/belt_tuner/motion_measure_dynamic",
            RequestType.POST, self._handle_motion_measure_dynamic
        )
        self.server.register_endpoint(
            "/server/belt_tuner/status", RequestType.GET, self._handle_status
        )
        self.server.register_endpoint(
            "/server/belt_tuner/clear", RequestType.POST, self._handle_clear
        )

    # ── Config helpers ──────────────────────────────────────────────────────────

    def _parse_calibration(self, config_str: str) -> List[Dict[str, float]]:
        """
        Parse '80:134, 100:110, 120:98' into [{'y':80,'freq':134}, ...].
        Returns [] if config_str is empty or unparseable.
        """
        result = []
        if not config_str.strip():
            return result
        for part in config_str.split(','):
            part = part.strip()
            if ':' in part:
                try:
                    y_str, f_str = part.split(':', 1)
                    result.append({'y': float(y_str.strip()), 'freq': float(f_str.strip())})
                except ValueError:
                    logger.warning(f"[belt_tuner] Skipping invalid calibration entry: {part!r}")
        result.sort(key=lambda e: e['y'])
        return result

    def _parse_probe_xz(self):
        """
        Extract X and Z from self.probe_point string (e.g. '175, 100, 20').
        Returns (x: float, z: float). Falls back to (175.0, 20.0) on error.
        """
        try:
            parts = [float(v.strip()) for v in self.probe_point.split(',')]
            if len(parts) >= 3:
                return parts[0], parts[2]
        except (ValueError, AttributeError):
            pass
        logger.warning('[belt_tuner] Could not parse probe_point X/Z; defaulting to 175, 20')
        return 175.0, 20.0

    # ── CSV lookup ──────────────────────────────────────────────────────────────

    def _find_csv(self, name: str) -> Optional[str]:
        """
        Return the path of the most-recent CSV matching /tmp/raw_data_*_{name}.csv,
        or None if no match found.
        """
        matches = sorted(
            glob.glob(f"/tmp/raw_data_*_{name}.csv"),
            key=os.path.getmtime
        )
        return matches[-1] if matches else None

    # ── Pluck-based measurement ─────────────────────────────────────────────────

    async def _handle_measure(self, web_request: WebRequest) -> Dict[str, Any]:
        belt = web_request.get_str('belt', 'A').upper()
        if belt not in ('A', 'B'):
            raise self.server.error("Belt must be 'A' or 'B'", 400)
        if self._measure_lock.locked():
            raise self.server.error("Measurement already in progress", 503)

        async with self._measure_lock:
            self._measuring = True
            self._status[belt]['error'] = None
            try:
                result = await self._do_measure(belt)
                self._status[belt] = result
                return result  # Moonraker wraps as {"result": <result>}
            except Exception as e:
                error_result = dict(EMPTY_RESULT)
                error_result['error'] = str(e)
                self._status[belt] = error_result
                raise
            finally:
                self._measuring = False

    async def _do_measure(self, belt: str) -> Dict[str, Any]:
        csv_name = f"belt_web_{belt}"
        csv_path = f"/tmp/adxl345-{csv_name}.csv"

        try:
            os.remove(csv_path)
        except FileNotFoundError:
            pass

        # Start recording — user should pluck the belt during the 3.5 s window
        await self.klippy_apis.run_gcode("ACCELEROMETER_MEASURE CHIP=adxl345")
        await asyncio.sleep(3.5)
        # Stop recording; Klipper saves to /tmp/adxl345-{csv_name}.csv
        await self.klippy_apis.run_gcode(
            f"ACCELEROMETER_MEASURE CHIP=adxl345 NAME={csv_name}"
        )
        await asyncio.sleep(0.5)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._run_analyzer, csv_path, belt)
        return result

    def _run_analyzer(self, csv_path: str, belt: str) -> Dict[str, Any]:
        for path in ANALYZER_SEARCH_PATHS:
            if os.path.exists(os.path.join(path, "belt_analyzer_v3.py")):
                if path not in sys.path:
                    sys.path.insert(0, path)
                break

        try:
            from belt_analyzer_v3 import analyze_pluck_event
        except ImportError as e:
            result = dict(EMPTY_RESULT)
            result['error'] = f"Import error: {e}"
            return result

        if not os.path.exists(csv_path):
            result = dict(EMPTY_RESULT)
            result['error'] = f"CSV not found at {csv_path}"
            return result

        return analyze_pluck_event(csv_path, belt)

    # ── Single-position motion scan ─────────────────────────────────────────────

    async def _handle_motion_measure(self, web_request: WebRequest) -> Dict[str, Any]:
        belt = web_request.get_str('belt', 'A').upper()
        freq_min = web_request.get_float('freq_min', 85.0)
        freq_max = web_request.get_float('freq_max', 140.0)
        if belt not in ('A', 'B'):
            raise self.server.error("Belt must be 'A' or 'B'", 400)
        if self._measure_lock.locked():
            raise self.server.error("Measurement already in progress", 503)

        async with self._measure_lock:
            self._measuring = True
            try:
                result = await self._do_motion_measure(belt, freq_min, freq_max)
                self._status[belt] = result
                return result
            except Exception as e:
                error_result = dict(EMPTY_RESULT)
                error_result['error'] = str(e)
                self._status[belt] = error_result
                raise
            finally:
                self._measuring = False

    async def _do_motion_measure(self, belt: str, freq_min: float, freq_max: float) -> Dict[str, Any]:
        axis = self.axis_a if belt == 'A' else self.axis_b
        name = f"belt_{belt.lower()}"
        point_arg = f" POINT={self.probe_point.replace(' ', '')}" if self.probe_point else ""
        gcode = (
            f"TEST_RESONANCES AXIS={axis} OUTPUT=raw_data NAME={name}"
            f" FREQ_START={freq_min:.1f} FREQ_END={freq_max:.1f} HZ_PER_SEC=2{point_arg}"
        )
        await self.klippy_apis.run_gcode(gcode)
        await asyncio.sleep(0.5)  # ensure file is flushed

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._run_sweep_analyzer, name, belt, axis, freq_min, freq_max
        )
        return result

    def _run_sweep_analyzer(self, name: str, belt: str, axis: str,
                            freq_min: float, freq_max: float) -> Dict[str, Any]:
        csv_path = self._find_csv(name)
        if not csv_path:
            result = dict(EMPTY_RESULT)
            result['error'] = f"No CSV found matching /tmp/raw_data_*_{name}.csv"
            return result

        for path in ANALYZER_SEARCH_PATHS:
            if os.path.exists(os.path.join(path, "belt_sweep_analyzer.py")):
                if path not in sys.path:
                    sys.path.insert(0, path)
                break

        try:
            from belt_sweep_analyzer import analyze_sweep_csv
        except ImportError as e:
            result = dict(EMPTY_RESULT)
            result['error'] = f"Import error: {e}"
            return result

        return analyze_sweep_csv(csv_path, belt, freq_min=freq_min, freq_max=freq_max, axis=axis)

    # ── Multi-position dynamic scan ─────────────────────────────────────────────

    async def _handle_motion_measure_dynamic(self, web_request: WebRequest) -> Dict[str, Any]:
        belt = web_request.get_str('belt', 'A').upper()
        y_positions = web_request.get('y_positions', [80, 100, 120])
        if not isinstance(y_positions, list):
            y_positions = [80, 100, 120]
        y_positions = [float(y) for y in y_positions]

        if belt not in ('A', 'B'):
            raise self.server.error("Belt must be 'A' or 'B'", 400)
        if self._measure_lock.locked():
            raise self.server.error("Measurement already in progress", 503)

        async with self._measure_lock:
            self._measuring = True
            self._dyn_progress = None
            try:
                result = await self._do_motion_measure_dynamic(belt, y_positions)
                self._status[belt] = result
                return result
            except Exception as e:
                error_result = dict(EMPTY_RESULT)
                error_result['error'] = str(e)
                self._status[belt] = error_result
                raise
            finally:
                self._measuring = False
                self._dyn_progress = None

    async def _do_motion_measure_dynamic(self, belt: str,
                                          y_positions: List[float]) -> Dict[str, Any]:
        axis = self.axis_a if belt == 'A' else self.axis_b
        calibration = self._calibration_a if belt == 'A' else self._calibration_b
        probe_x, probe_z = self._parse_probe_xz()
        n = len(y_positions)
        scans: List[Dict[str, Any]] = []

        loop = asyncio.get_event_loop()

        for i, y in enumerate(y_positions):
            self._dyn_progress = f'{i + 1}/{n}'
            name = f"belt_{belt.lower()}_y{int(y)}"
            point_str = f"{probe_x:.0f},{y:.0f},{probe_z:.0f}"
            gcode = (
                f"TEST_RESONANCES AXIS={axis} OUTPUT=raw_data NAME={name}"
                f" FREQ_START=85.0 FREQ_END=140.0 HZ_PER_SEC=2"
                f" POINT={point_str}"
            )
            logger.info(f"[belt_tuner] Dynamic scan {i+1}/{n}: Y={y:.0f} → {gcode}")
            await self.klippy_apis.run_gcode(gcode)
            await asyncio.sleep(0.5)

            csv_path = await loop.run_in_executor(None, self._find_csv, name)
            if csv_path is None:
                result = dict(EMPTY_RESULT)
                result['error'] = f"No CSV found for Y={y:.0f} scan (NAME={name})"
                return result
            scans.append({'y_pos': y, 'filepath': csv_path})

        result = await loop.run_in_executor(
            None, self._run_multi_position_analyzer,
            scans, belt, axis, calibration
        )
        return result

    def _run_multi_position_analyzer(self, scans: List[Dict[str, Any]], belt: str,
                                      axis: str,
                                      calibration: List[Dict[str, float]]) -> Dict[str, Any]:
        for path in ANALYZER_SEARCH_PATHS:
            if os.path.exists(os.path.join(path, "belt_sweep_analyzer.py")):
                if path not in sys.path:
                    sys.path.insert(0, path)
                break

        try:
            from belt_sweep_analyzer import analyze_multi_position_sweep
        except ImportError as e:
            result = dict(EMPTY_RESULT)
            result['error'] = f"Import error: {e}"
            return result

        return analyze_multi_position_sweep(
            scans, belt_name=belt, axis=axis,
            calibration=calibration if calibration else None
        )

    # ── Status / clear ──────────────────────────────────────────────────────────

    async def _handle_status(self, web_request: WebRequest) -> Dict[str, Any]:
        return {
            'status':       self._status,
            'measuring':    self._measuring,
            'dyn_progress': self._dyn_progress,
        }

    async def _handle_clear(self, web_request: WebRequest) -> Dict[str, Any]:
        belt = web_request.get_str('belt', '').upper()
        if belt in ('A', 'B'):
            self._status[belt] = dict(EMPTY_RESULT)
        else:
            self._status['A'] = dict(EMPTY_RESULT)
            self._status['B'] = dict(EMPTY_RESULT)
        return {'result': 'cleared'}


def load_component(config: ConfigHelper) -> BeltTuner:
    return BeltTuner(config)
