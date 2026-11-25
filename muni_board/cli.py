"""Command-line entry point."""

import argparse
import os
from tempfile import NamedTemporaryFile
import json
import sys
import time
from pathlib import Path

from .api import ApiError, fetch_stop, parse_511_time
from .core import PayloadError, build_board, monitored_visits
from .render import render_human, render_json, render_matrix
from .settings import SettingsError, load_settings


def _parser():
    parser = argparse.ArgumentParser(
        description="Show 511 SF Bay arrivals for two configured stops and routes"
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--matrix", action="store_true", help="show the 64 x 32 text model")
    output.add_argument("--json", action="store_true", help="print the board model as JSON")
    parser.add_argument("--watch", action="store_true", help="refresh continuously")
    parser.add_argument(
        "--save-raw",
        metavar="DIRECTORY",
        help="save the latest responses for debugging; request URLs and the token are not saved",
    )
    return parser


def _save_raw(directory, stop_key, payload):
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    target = path / f"{stop_key}.json"
    with NamedTemporaryFile(mode="w", dir=path, encoding="utf-8", delete=False) as temp:
        temporary_path = Path(temp.name)
        try:
            json.dump(payload, temp, indent=2, sort_keys=True)
            temp.close()
            os.replace(temporary_path, target)
        finally:
            temporary_path.unlink(missing_ok=True)


def fetch_cycle(settings, cached_payloads=None, save_raw=None):
    payloads = dict(cached_payloads or {})
    errors = {}
    fresh_keys = set()

    for stop in settings["stops"]:
        try:
            payload = fetch_stop(
                settings["token"],
                stop["agency"],
                stop["stop_code"],
                timeout_seconds=settings["timeout_seconds"],
            )
            monitored_visits(payload)
            payloads[stop["key"]] = payload
            fresh_keys.add(stop["key"])
            if save_raw:
                _save_raw(save_raw, stop["key"], payload)
        except (ApiError, PayloadError) as exc:
            errors[stop["key"]] = str(exc)

    now_epoch = time.time()
    try:
        board = build_board(
            payloads,
            settings,
            now_epoch,
            parse_511_time,
            errors=errors,
        )
    except PayloadError as exc:
        raise ApiError(str(exc)) from exc
    return board, payloads, fresh_keys


def _render(board, args):
    if args.json:
        return render_json(board)
    if args.matrix:
        return render_matrix(board)
    return render_human(board)


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        settings = load_settings()
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    cached_payloads = {}
    while True:
        try:
            board, cached_payloads, fresh_keys = fetch_cycle(
                settings, cached_payloads, args.save_raw
            )
        except ApiError as exc:
            print(f"Data error: {exc}", file=sys.stderr)
            return 1

        print(_render(board, args), flush=True)
        if not args.watch:
            return 0 if len(fresh_keys) == len(settings["stops"]) else 1

        print(f"\nNext refresh in {settings['poll_seconds']} seconds.\n", flush=True)
        try:
            time.sleep(settings["poll_seconds"])
        except KeyboardInterrupt:
            return 0
