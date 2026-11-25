import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from muni_board.api import ApiError, parse_511_time
from tools import live

PAYLOAD = json.loads(
    (Path(__file__).parent / "fixtures/stop_monitoring.json").read_text(encoding="utf-8")
)
NOW = parse_511_time("2025-01-02T00:00:00Z")


class LiveTests(unittest.TestCase):
    def test_shows_one_route_with_the_board_text(self):
        text = "\n".join(live.stop_lines(PAYLOAD, "SF", "1", "38", NOW))
        self.assertIn("board shows: 4:00 12", text)
        self.assertIn("Library", text)
        if live.PACIFIC:
            self.assertIn("16:04:00 PST", text)

    def test_shows_every_route_by_default(self):
        text = "\n".join(live.stop_lines(PAYLOAD, "SF", "1", None, NOW))
        self.assertIn("Route 38", text)
        self.assertIn("Route 77", text)

    def test_one_failed_stop_does_not_hide_the_other(self):
        with (
            patch.dict(os.environ, {"TRANSIT_511_TOKEN": "private"}),
            patch.object(live, "fetch_stop", side_effect=[ApiError("511 returned HTTP 401"), PAYLOAD]),
            patch.object(live.time, "time", return_value=NOW),
            redirect_stdout(io.StringIO()) as output,
            redirect_stderr(io.StringIO()) as errors,
        ):
            self.assertEqual(1, live.main(["1", "2"]))
        self.assertIn("Stop 1: 511 returned HTTP 401", errors.getvalue())
        self.assertIn("Stop 2", output.getvalue())
        self.assertNotIn("private", output.getvalue() + errors.getvalue())


if __name__ == "__main__":
    unittest.main()
