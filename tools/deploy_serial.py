#!/usr/bin/env python3
"""Update the firmware on a board through its USB serial console.

Stop the running program with Ctrl-C and press Enter for a >>> prompt, then close the
console and run this. It leaves settings.toml and lib alone.
"""

import argparse
import base64
import os
import select
import time
from pathlib import Path


PROMPT = b">>>"
# Keep the complete generated REPL command below CircuitPython's input buffer.
CHUNK_CHARS = 16
FILES = ("board_config.py", "board_layout.py", "diagnostics.py", "muni_logic.py", "code.py")


class SerialRepl:
    def __init__(self, device):
        self.fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.device = device
        self.buffer = b""

    def close(self):
        os.close(self.fd)

    def send(self, text):
        data = text.encode("ascii")
        offset = 0
        while offset < len(data):
            offset += os.write(self.fd, data[offset:])
        time.sleep(0.02)

    def read_until_prompt(self, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            prompt_at = self.buffer.find(PROMPT)
            if prompt_at >= 0:
                output = self.buffer[:prompt_at] + PROMPT
                self.buffer = self.buffer[prompt_at + len(PROMPT) :]
                return output
            remaining = deadline - time.monotonic()
            readable, _, _ = select.select([self.fd], [], [], min(0.25, remaining))
            if not readable:
                continue
            chunk = os.read(self.fd, 4096)
            if chunk:
                self.buffer += chunk
        raise TimeoutError("timed out waiting for CircuitPython REPL prompt")

    def command(self, text):
        self.send(text + "\r")
        output = self.read_until_prompt()
        if b"Traceback" in output or b"Error" in output:
            raise RuntimeError(output.decode("utf-8", errors="replace"))
        return output


def deploy_file(repl, source, target):
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    repl.command("open(" + repr(target) + ", 'wb').close()")
    for start in range(0, len(encoded), CHUNK_CHARS):
        chunk = encoded[start : start + CHUNK_CHARS]
        repl.command(
            "f=open("
            + repr(target)
            + ", 'ab'); f.write(binascii.a2b_base64("
            + repr(chunk)
            + ")); f.close()"
        )


def install_file(repl, name):
    if name in repl.command("print(os.listdir())").decode("utf-8", errors="replace").split("'"):
        repl.command("os.remove(" + repr(name) + ")")
    repl.command("os.rename(" + repr(name + ".new") + ", " + repr(name) + ")")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    repl = SerialRepl(args.device)
    try:
        repl.send("\r")
        repl.read_until_prompt()
        repl.command("import supervisor; supervisor.runtime.autoreload = False")
        repl.command("import storage; storage.remount('/', False)")
        repl.command("import binascii")
        # Upload everything before replacing anything, so a dropped connection leaves working files.
        for name in FILES:
            print("uploading " + name, flush=True)
            deploy_file(repl, args.root / "device" / name, name + ".new")
        repl.command("import os")
        for name in FILES:
            install_file(repl, name)
        print("reloading board", flush=True)
        repl.send("supervisor.reload()\r")
        time.sleep(2)
        try:
            print(repl.read_until_prompt(timeout=5).decode("utf-8", errors="replace"))
        except TimeoutError:
            # A successful reload runs code.py instead of returning to a prompt.
            print("board reloaded into code.py", flush=True)
    finally:
        repl.close()


if __name__ == "__main__":
    main()
