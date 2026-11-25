"""Run the firmware loop against a simulated clock, Wi-Fi radio, and 511 feed."""

import copy
import importlib.util
import io
import json
import sys
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "adafruit_connection_manager", "adafruit_requests", "board", "busio", "displayio",
    "framebufferio", "fontio", "microcontroller", "rgbmatrix", "terminalio",
    "adafruit_display_text", "adafruit_display_text.label", "adafruit_esp32spi",
    "digitalio", "watchdog", "diagnostics",
)


class Done(BaseException):
    """End a simulation. The firmware's `except Exception` must not catch it."""


class Simulation:
    def __init__(self, wifi=lambda t: True, api=lambda t: True, seconds=100, settings=None):
        self.now, self.seconds = 0.0, seconds
        self.wifi, self.api = wifi, api
        self.connected = False
        self.titles, self.rows = [], []
        self.payload = json.loads((ROOT / "tests/fixtures/stop_monitoring.json").read_text())
        self.settings = tomllib.loads((ROOT / "device/settings.toml.example").read_text())
        self.settings.update(
            CIRCUITPY_WIFI_SSID="wifi", CIRCUITPY_WIFI_PASSWORD="password",
            TRANSIT_511_TOKEN="token", BOARD_ROW1_STOP="1", BOARD_ROW2_STOP="2",
        )
        self.settings.update(settings or {})
        modules = {name: MagicMock() for name in MODULES}
        spec = importlib.util.spec_from_file_location("firmware", ROOT / "device/code.py")
        self.firmware = importlib.util.module_from_spec(spec)
        with (
            patch.dict(sys.modules, modules),
            patch.object(sys, "path", [str(ROOT / "device"), *sys.path]),
        ):
            spec.loader.exec_module(self.firmware)

    def sleep(self, seconds):
        if seconds < 0:
            raise ValueError("sleep length must be non-negative")
        self.now += seconds
        if self.now > self.seconds:
            raise Done

    def show(self, inbound=("", ""), outbound=("", ""), *, title):
        if not self.titles or self.titles[-1][1] != title:
            self.titles.append((int(self.now), title))
        self.rows.append((int(self.now), inbound, outbound))

    def get(self, url, **kwargs):
        if not self.api(self.now):
            raise OSError("timed out")
        return SimpleNamespace(
            status_code=200, json=lambda: copy.deepcopy(self.payload), close=lambda: None
        )

    def connect(self, ssid, password):
        self.connected = self.wifi(self.now)
        if not self.connected:
            raise ConnectionError

    def run(self):
        simulation = self

        class Radio:
            @property
            def is_connected(self):
                simulation.connected = simulation.connected and simulation.wifi(simulation.now)
                return simulation.connected

            connect_AP = staticmethod(simulation.connect)

        fw = self.firmware
        with (
            patch.object(fw, "time", SimpleNamespace(monotonic=lambda: self.now, sleep=self.sleep)),
            patch.object(fw, "os", SimpleNamespace(getenv=self.settings.get)),
            patch.object(fw, "make_display", return_value=(None, {})),
            patch.object(fw, "make_network", return_value=(Radio(), SimpleNamespace(get=self.get))),
            patch.object(fw, "show", self.show),
            redirect_stdout(io.StringIO()),
        ):
            try:
                fw.run()
            except Done:
                pass
        return [title for _, title in self.titles]


class FirmwareStateTests(unittest.TestCase):
    def test_missing_settings_stop_at_setup(self):
        self.assertEqual(["SETUP"], Simulation(settings={"TRANSIT_511_TOKEN": ""}).run())

    def test_wifi_retries_until_the_board_is_live(self):
        simulation = Simulation(wifi=lambda t: t >= 30)
        self.assertEqual(["CONNECT", "WIFI!", "CONNECT", "WIFI!", "CONNECT", "BUS"], simulation.run())

    def test_failed_fetches_show_api_err_then_stale_then_recover(self):
        simulation = Simulation(api=lambda t: t < 100 or t >= 1000, seconds=1200)
        self.assertEqual(["CONNECT", "BUS", "API ERR", "STALE", "BUS"], simulation.run())

    def test_slow_polling_is_not_stale_while_fetches_succeed(self):
        simulation = Simulation(seconds=2000, settings={"BOARD_POLL_SECONDS": 900})
        self.assertEqual(["CONNECT", "BUS"], simulation.run())

    def test_board_restarts_after_thirty_minutes_without_data(self):
        simulation = Simulation(api=lambda t: t < 100, seconds=4000)
        with self.assertRaises(RuntimeError):
            simulation.run()
        self.assertEqual((("NO DATA", ""), ("NO DATA", "")), simulation.rows[-1][1:])
        self.assertGreater(simulation.now, 1800)
        self.assertLess(simulation.now, 2000)

    def test_board_restarts_when_the_first_fetch_never_succeeds(self):
        with self.assertRaises(RuntimeError):
            Simulation(api=lambda t: False, seconds=4000).run()

    def test_one_working_row_prevents_a_restart(self):
        simulation = Simulation(seconds=4000)
        simulation.get = lambda url, **kwargs: (
            Simulation.get(simulation, url) if "stopCode=1&" in url else (_ for _ in ()).throw(OSError())
        )
        simulation.run()
        self.assertEqual(("NO DATA", ""), simulation.rows[-1][2])

    def test_sleep_tolerates_the_deadline_passing_before_the_remaining_time_is_read(self):
        simulation = Simulation()
        fw = simulation.firmware
        clock = iter([0, 0.999, 1.001, 1.002])
        with patch.object(
            fw, "time", SimpleNamespace(monotonic=lambda: next(clock), sleep=simulation.sleep)
        ):
            fw.sleep_with_watchdog(1)

    def test_request_retries_fit_inside_the_watchdog_window(self):
        fw = Simulation().firmware
        # adafruit_requests waits for a response twice before raising.
        self.assertLess(2 * fw.REQUEST_TIMEOUT, fw.WATCHDOG_TIMEOUT - 4)


if __name__ == "__main__":
    unittest.main()
