"""Show live 511 arrivals for any stop, and what the board would display."""

import argparse
import os
import sys
import time
from datetime import datetime
from getpass import getpass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from device.muni_logic import arrival_pair_texts, parse_remaining_seconds
from muni_board.api import ApiError, fetch_stop, parse_511_time
from muni_board.core import PayloadError, parse_arrivals, route_choices
from muni_board.render import terminal_text
from muni_board.settings import load_env_file

try:
    PACIFIC = ZoneInfo("America/Los_Angeles")
except ZoneInfoNotFoundError:
    PACIFIC = None  # Windows may have no time zone data. Use the computer's time zone.


def clock(epoch):
    return datetime.fromtimestamp(epoch, PACIFIC).astimezone(PACIFIC).strftime("%H:%M:%S %Z")


def countdown(seconds):
    sign, seconds = ("-" if seconds < 0 else ""), abs(int(seconds))
    return f"{sign}{seconds // 60}:{seconds % 60:02d}"


def stop_lines(payload, agency, stop_code, route, now):
    """Return the text for one stop. Raise PayloadError if 511 rejected the request."""
    lines = [f"Stop {terminal_text(stop_code)} ({terminal_text(agency)})"]
    routes = [route] if route else list(route_choices(payload))
    if not routes:
        lines.append("  No arrivals reported.")
    for name in routes:
        stop = {"route": name, "key": "stop", "stop_code": stop_code}
        arrivals = parse_arrivals(payload, stop, now, parse_511_time)
        board = " ".join(filter(None, arrival_pair_texts(parse_remaining_seconds(payload, name))))
        lines.append(f"  Route {terminal_text(name)}   board shows: {board}")
        if not arrivals:
            lines.append("    No arrivals reported.")
            continue
        lines.append(f"    {'Time':<12} {'In':>6}  {'Report age':>10}  Destination")
        for arrival in arrivals:
            recorded = arrival["recorded_epoch"]
            # 511 uses 1970 when there is no vehicle report.
            age = countdown(now - recorded) if recorded and recorded > 86400 else "none"
            lines.append(
                f"    {clock(arrival['eta_epoch']):<12} {countdown(arrival['eta_epoch'] - now):>6}  {age:>10}  "
                f"{terminal_text(arrival['destination'])}"
            )
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stops", nargs="+", metavar="STOP", help="511 stop ID")
    parser.add_argument("--route", help="show one route, such as N")
    parser.add_argument("--agency", default="SF", help="511 agency code (default: SF for Muni)")
    parser.add_argument("--env", type=Path, help="file that holds TRANSIT_511_TOKEN (default: .env)")
    args = parser.parse_args(argv)

    load_env_file(args.env)
    token = os.environ.get("TRANSIT_511_TOKEN", "").strip()
    if not token and sys.stdin.isatty():
        token = getpass("511 API token (hidden, not saved): ").strip()
    if not token:
        print("TRANSIT_511_TOKEN is missing. Run python3 tools/setup.py first.", file=sys.stderr)
        return 2

    failed = False
    for stop_code in args.stops:
        try:
            payload = fetch_stop(token, args.agency, stop_code)
            lines = stop_lines(payload, args.agency, stop_code, args.route, time.time())
            print("\n".join(lines))
        except (ApiError, PayloadError) as error:
            failed = True
            print(f"Stop {terminal_text(stop_code)}: {terminal_text(str(error))}", file=sys.stderr)
    print(f"Checked {clock(time.time())}. Data provided by 511.org.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
