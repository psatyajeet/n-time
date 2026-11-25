"""Shared 511 stop and layout configuration for Python and CircuitPython."""

ROW_CHARACTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -"
DISPLAY_CHARACTERS = ROW_CHARACTERS + "/&."


class SettingsError(ValueError):
    """A missing or invalid setting."""


def _required(getenv, name):
    value = str(getenv(name) or "").strip()
    if not value:
        raise SettingsError(name + " is required")
    return value


def _display_text(getenv, name, width, characters):
    value = _required(getenv, name).upper()
    if len(value) > width or any(char not in characters for char in value):
        raise SettingsError(name + " must be 1 to " + str(width) + " display characters")
    return value


def load_board_config(getenv):
    """Read the same keys from the laptop environment and device settings.toml."""
    try:
        poll_seconds = int(getenv("BOARD_POLL_SECONDS") or 150)
    except (TypeError, ValueError):
        raise SettingsError("BOARD_POLL_SECONDS must be an integer")
    if poll_seconds < 30:
        raise SettingsError("BOARD_POLL_SECONDS must be at least 30")

    rows = []
    for number in (1, 2):
        prefix = "BOARD_ROW" + str(number) + "_"
        rows.append(
            {
                "key": "row" + str(number),
                "agency": _required(getenv, prefix + "AGENCY"),
                "stop_code": _required(getenv, prefix + "STOP"),
                "route": _required(getenv, prefix + "ROUTE"),
                "label": _display_text(getenv, prefix + "LABEL", 4, ROW_CHARACTERS),
            }
        )
    return {
        "badge": _display_text(getenv, "BOARD_BADGE", 2, DISPLAY_CHARACTERS),
        "title": _display_text(getenv, "BOARD_TITLE", 8, DISPLAY_CHARACTERS),
        "stops": rows,
        "poll_seconds": poll_seconds,
    }


def query_value(value):
    """Encode a URL query value without urllib on CircuitPython."""
    safe = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    return "".join(chr(byte) if byte in safe else "%%%02X" % byte for byte in value.encode("utf-8"))
