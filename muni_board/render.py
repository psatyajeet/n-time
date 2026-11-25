"""Render the board as terminal text or JSON."""

import json
from datetime import datetime

from .core import minutes_until


def terminal_text(value):
    return "".join(char if char.isprintable() else ascii(char)[1:-1] for char in value)


def _clock(epoch):
    value = datetime.fromtimestamp(epoch).astimezone()
    hour = value.hour % 12 or 12
    return f"{hour}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"


def _eta_text(arrivals, now_epoch, empty="--"):
    if not arrivals:
        return empty
    values = []
    for arrival in arrivals:
        minutes = minutes_until(arrival["eta_epoch"], now_epoch)
        values.append("DUE" if minutes == 0 else str(minutes))
    return "  ".join(values)


def render_matrix(board):
    """Render the text shown on the 64 x 32 panel."""
    now_epoch = board["generated_epoch"]
    lines = [f"{board['badge']} {board['title']}"]
    for row in board["directions"].values():
        lines.append(f"{row['label']}  {_eta_text(row['arrivals'], now_epoch)}")
    return "\n".join(lines)


def render_human(board):
    now_epoch = board["generated_epoch"]
    lines = [f"{board['badge']} {board['title']}"]
    for direction in board["directions"].values():
        arrivals = direction["arrivals"]
        if arrivals:
            details = []
            for arrival in arrivals:
                minutes = minutes_until(arrival["eta_epoch"], now_epoch)
                eta = "due" if minutes == 0 else f"{minutes} min"
                details.append(f"{eta} to {terminal_text(arrival['destination'])}")
            result = "; ".join(details)
        else:
            result = "no predictions"
        lines.append(
            f"{direction['label']} ({terminal_text(direction['agency'])} route {terminal_text(direction['route'])}, "
            f"stop {terminal_text(direction['stop_code'])}): {result}"
        )

    for key, message in board.get("errors", {}).items():
        lines.append(f"{key.title()} data warning: {terminal_text(message)}")
    lines.append(f"Updated {_clock(now_epoch)}")
    lines.append(board["attribution"])
    return "\n".join(lines)


def render_json(board):
    return json.dumps(board, indent=2, sort_keys=True)
