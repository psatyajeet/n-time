"""Deploy against a fake console that runs the same commands on a folder."""

import binascii
import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

if sys.platform != "win32":
    from tools import deploy_serial

ROOT = Path(__file__).resolve().parents[1]


class FakeRepl:
    def __init__(self, folder, fail_after=None):
        self.folder, self.count, self.fail_after = folder, 0, fail_after
        self.names = {
            "binascii": binascii,
            "open": lambda name, mode: open(folder / name, mode),
            "os": SimpleNamespace(
                listdir=lambda: os.listdir(folder),
                remove=lambda name: os.remove(folder / name),
                rename=self.rename,
            ),
        }

    def rename(self, old, new):
        if (self.folder / new).exists():
            raise OSError("File exists")
        os.rename(self.folder / old, self.folder / new)

    def command(self, text):
        self.count += 1
        if self.fail_after and self.count > self.fail_after:
            raise TimeoutError
        if text.startswith("import "):
            return b""
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(text, self.names)
        return output.getvalue().encode()

    def send(self, text):
        pass

    def read_until_prompt(self, timeout=10):
        return b">>>"

    def close(self):
        pass


@unittest.skipIf(sys.platform == "win32", "serial deployment needs macOS or Linux")
class DeploySerialTests(unittest.TestCase):
    def deploy(self, folder, fail_after=None):
        repl = FakeRepl(folder, fail_after)
        with (
            patch.object(deploy_serial, "SerialRepl", return_value=repl),
            patch.object(deploy_serial.time, "sleep"),
            patch.object(sys, "argv", ["deploy", "--device", "port", "--root", str(ROOT)]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            deploy_serial.main()

    def test_replaces_firmware_and_keeps_settings(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "code.py").write_text("old")
            (folder / "settings.toml").write_text("private")
            self.deploy(folder)
            self.assertEqual(
                {*deploy_serial.FILES, "settings.toml"}, {p.name for p in folder.iterdir()}
            )
            for name in deploy_serial.FILES:
                self.assertEqual((ROOT / "device" / name).read_bytes(), (folder / name).read_bytes())
            self.assertEqual("private", (folder / "settings.toml").read_text())

    def test_interrupted_upload_keeps_the_old_firmware(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "code.py").write_text("old")
            with self.assertRaises(TimeoutError):
                self.deploy(folder, fail_after=50)
            self.assertEqual("old", (folder / "code.py").read_text())


if __name__ == "__main__":
    unittest.main()
