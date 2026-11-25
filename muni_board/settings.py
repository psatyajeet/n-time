"""Configuration and local secret loading."""

import os
from pathlib import Path

from device.board_config import SettingsError, load_board_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent


ENV_KEYS = {"TRANSIT_511_TOKEN", "BOARD_POLL_SECONDS", "BOARD_HTTP_TIMEOUT_SECONDS",
            "BOARD_BADGE", "BOARD_TITLE"} | {
    f"BOARD_ROW{row}_{field}"
    for row in (1, 2)
    for field in ("AGENCY", "STOP", "ROUTE", "LABEL")
}


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def load_env_file(path=None):
    """Load a small KEY=VALUE file without adding a runtime dependency."""
    path = Path(path or PROJECT_ROOT / ".env")
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in ENV_KEYS and key not in os.environ:
            os.environ[key] = _unquote(value)


def _positive_int(name, default):
    raw_value = os.environ.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer") from exc
    if value <= 0:
        raise SettingsError(f"{name} must be positive")
    return value


def load_settings(env_path=None):
    load_env_file(env_path)

    token = os.environ.get("TRANSIT_511_TOKEN", "").strip()
    if not token:
        raise SettingsError(
            "TRANSIT_511_TOKEN is missing. Run python3 tools/setup.py or add the token to .env."
        )

    settings = load_board_config(os.environ.get)
    settings["token"] = token
    settings["timeout_seconds"] = _positive_int("BOARD_HTTP_TIMEOUT_SECONDS", 15)
    return settings
