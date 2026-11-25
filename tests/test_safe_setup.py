import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from muni_board.cli import _save_raw
from muni_board.render import terminal_text
from muni_board.settings import SettingsError, load_env_file
from tools import setup


class SafeSetupTests(unittest.TestCase):
    def test_env_ignores_unrelated_keys(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            path = Path(directory) / ".env"
            path.write_text("UNRELATED_SETTING=1\nBOARD_BADGE=N\n")
            load_env_file(path)
            self.assertNotIn("UNRELATED_SETTING", os.environ)
            self.assertEqual("N", os.environ["BOARD_BADGE"])

    def test_route_with_line_separator_cannot_be_saved(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            with (
                patch.object(setup, "secret", return_value="example"),
                patch.object(setup, "prompt", return_value="SF"),
                patch.object(setup, "fetch_stop", return_value={}),
                patch.object(setup, "route_choices", return_value={}),
                patch.object(setup, "choose_route", return_value="N\u2028Judah"),
                redirect_stdout(io.StringIO()),
                self.assertRaises(SettingsError),
            ):
                setup.setup_stops(path, False)
            self.assertFalse(path.exists())

    def test_terminal_display_preserves_printable_unicode(self):
        self.assertEqual("Café\\nJudah", terminal_text("Café\nJudah"))

    @unittest.skipIf(os.name == "nt", "symlink creation may require Windows privileges")
    def test_raw_export_replaces_the_directory_entry(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original"
            original.write_text("keep")
            target = root / "row1.json"
            target.symlink_to(original)
            _save_raw(root, "row1", {"ok": True})
            self.assertEqual("keep", original.read_text())
            self.assertFalse(target.is_symlink())
            self.assertEqual({"ok": True}, json.loads(target.read_text()))

    @unittest.skipUnless(os.name == "posix", "USB collector uses POSIX serial APIs")
    def test_serial_collector_resumes_after_an_oversized_line(self):
        from tools import capture_serial as serial

        chunks = iter([b"x" * 4096] * 4 + [b"end\nnext\n"])

        def read_chunk(fd, size):
            chunk = next(chunks)
            if chunk.endswith(b"next\n"):
                serial.STOP = True
            return chunk

        with TemporaryDirectory() as directory:
            log = Path(directory) / "capture.log"
            with (
                patch.object(serial, "STOP", False),
                patch.object(serial, "configure"),
                patch.object(serial.os, "open", return_value=42),
                patch.object(serial.os, "close"),
                patch.object(serial.os, "read", side_effect=read_chunk),
                patch.object(serial.select, "select", return_value=([42], [], [])),
            ):
                serial.capture("test-device", log, 0)
            records = log.read_text().splitlines()
            self.assertTrue(any(line.endswith("x" * serial.MAX_LINE_BYTES) for line in records))
            self.assertTrue(any(line.endswith("] next") for line in records))
            self.assertFalse(any(line.endswith("end") for line in records))

    def test_prepare_assembles_a_private_folder_from_saved_stops(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle" / "lib"
            bundle.mkdir(parents=True)
            for name in setup.BOARD_LIBRARIES:
                if name.endswith(".mpy"):
                    (bundle / name).write_bytes(b"module")
                else:
                    (bundle / name).mkdir()
                    (bundle / name / "__init__.mpy").write_bytes(b"package")
            project = setup.PROJECT_ROOT
            (root / "device").mkdir()
            for name in setup.BOARD_FILES:
                (root / "device" / name).write_bytes((project / "device" / name).read_bytes())
            (root / ".env").write_text((project / ".env.example").read_text().replace(
                "TOKEN=", "TOKEN=test"
            ).replace("_STOP=", "_STOP=123"))
            with (
                patch.object(setup, "PROJECT_ROOT", root),
                patch.dict(os.environ, {}, clear=True),
                patch.object(setup, "prompt", return_value="Example network"),
                patch.object(setup, "secret", return_value="Example password"),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(0, setup.main(["--prepare", str(bundle.parent)]))
            folder, = root.glob("Transit-Glow-board-*")
            self.assertEqual(set(setup.BOARD_FILES) | {"lib", "settings.toml"},
                             {file.name for file in folder.iterdir()})
            self.assertEqual(set(setup.BOARD_LIBRARIES), {file.name for file in (folder / "lib").iterdir()})
            self.assertIn('CIRCUITPY_WIFI_PASSWORD = "Example password"', (folder / "settings.toml").read_text())
            if os.name == "posix":
                self.assertEqual(0, folder.stat().st_mode & 0o077)
