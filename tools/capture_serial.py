#!/usr/bin/env python3
"""Capture CircuitPython USB serial output with host timestamps."""

import argparse
import os
import select
import signal
import termios
import time
from datetime import datetime
from pathlib import Path

MAX_LINE_BYTES = 8192
STOP = False


def stop(_signum, _frame):
    global STOP
    STOP = True


def timestamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def configure(fd):
    try:
        attributes = termios.tcgetattr(fd)
        attributes[0] = 0
        attributes[1] = 0
        attributes[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attributes[3] = 0
        attributes[4] = termios.B115200
        attributes[5] = termios.B115200
        termios.tcsetattr(fd, termios.TCSANOW, attributes)
    except termios.error:
        # USB CDC devices can already be configured by macOS, and managed
        # environments may forbid changing their termios settings.
        pass


def write_record(log, text):
    log.write("[" + timestamp() + "] " + text + "\n")
    log.flush()


def capture(device, log_path, retry_seconds):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", buffering=1) as log:
        write_record(log, "collector_started device=" + device)
        waiting_logged = False
        while not STOP:
            fd = None
            try:
                fd = os.open(device, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
                configure(fd)
                write_record(log, "serial_connected")
                waiting_logged = False
                pending = b""
                discarding = False
                while not STOP:
                    readable, _, _ = select.select([fd], [], [], 5)
                    if not readable:
                        continue
                    chunk = os.read(fd, 4096)
                    if not chunk:
                        raise OSError("serial device disconnected")
                    if discarding:
                        _, newline, chunk = chunk.partition(b"\n")
                        if not newline:
                            continue
                        discarding = False
                    pending += chunk
                    lines = pending.split(b"\n")
                    pending = lines.pop()
                    for line in lines:
                        write_record(log, line[:MAX_LINE_BYTES].decode("utf-8", errors="replace").rstrip("\r"))
                    if len(pending) > MAX_LINE_BYTES:
                        write_record(log, pending[:MAX_LINE_BYTES].decode("utf-8", errors="replace"))
                        pending = b""
                        discarding = True
                if pending:
                    write_record(log, "partial=" + pending.decode("utf-8", errors="replace"))
            except (FileNotFoundError, OSError) as error:
                if not STOP and not waiting_logged:
                    write_record(log, "serial_wait error=" + type(error).__name__)
                    waiting_logged = True
                if not STOP:
                    time.sleep(retry_seconds)
            finally:
                if fd is not None:
                    os.close(fd)
        write_record(log, "collector_stopped")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument(
        "--log",
        default=str(Path(__file__).resolve().parents[1] / "var" / "serial.log"),
    )
    parser.add_argument("--retry-seconds", type=float, default=2)
    args = parser.parse_args()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    capture(args.device, Path(args.log), args.retry_seconds)


if __name__ == "__main__":
    main()
