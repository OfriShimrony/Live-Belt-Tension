"""
Moonraker component for Live Belt Tension.

Deploy to: ~/moonraker/moonraker/components/belt_tuner.py
Activate by adding [belt_tuner] to moonraker.conf.

Exposes:
  POST /server/belt_tuner/measure  {"belt": "A"}
  GET  /server/belt_tuner/status
  POST /server/belt_tuner/clear    {"belt": "A"}  (omit belt to clear both)
"""

from __future__ import annotations
import asyncio
import logging
import os
import sys

from ..common import RequestType

from typing import TYPE_CHECKING, Any, Dict

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
        self._status: Dict[str, Any] = {
            'A': dict(EMPTY_RESULT),
            'B': dict(EMPTY_RESULT),
        }
        self._measuring = False
        self._measure_lock = asyncio.Lock()

        self.server.register_endpoint(
            "/server/belt_tuner/measure", RequestType.POST, self._handle_measure
        )
        self.server.register_endpoint(
            "/server/belt_tuner/status", RequestType.GET, self._handle_status
        )
        self.server.register_endpoint(
            "/server/belt_tuner/clear", RequestType.POST, self._handle_clear
        )

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

    async def _handle_status(self, web_request: WebRequest) -> Dict[str, Any]:
        return {'status': self._status, 'measuring': self._measuring}

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
