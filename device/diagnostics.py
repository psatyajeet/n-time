"""Event log saved to flash so it can be read after a reset."""

import os
import time

import microcontroller
import supervisor

LOG_PATH = "/muni-diagnostics.log"
MAX_LOG_BYTES = 32768


def _name(value):
    """Return a compact enum name without depending on enum formatting."""
    text = str(value)
    return text.rsplit(".", 1)[-1]


def _context():
    try:
        reset = _name(microcontroller.cpu.reset_reason)
    except Exception:
        reset = "UNAVAILABLE"
    try:
        run = _name(supervisor.runtime.run_reason)
    except Exception:
        run = "UNAVAILABLE"
    return reset, run


def _line(event, details):
    reset, run = _context()
    fields = [
        "t=" + str(int(time.monotonic())),
        "event=" + event,
        "reset=" + reset,
        "run=" + run,
    ]
    for key, value in details.items():
        fields.append(str(key) + "=" + str(value))
    return " ".join(fields) + "\n"


def record(event, **details):
    """Append one record. A failed write prints a message and the board keeps running."""
    line = _line(event, details)
    try:
        try:
            mode = "w" if os.stat(LOG_PATH)[6] > MAX_LOG_BYTES else "a"
        except OSError:
            mode = "a"
        with open(LOG_PATH, mode) as log:
            log.write(line)
    except Exception as error:
        print("Diagnostics write failed: " + type(error).__name__)
    return line.rstrip()


def boot():
    """Save and print the reset cause at the start of every run."""
    line = record("boot")
    print("MUNI " + line)
