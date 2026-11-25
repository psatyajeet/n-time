"""Find routes for your stops and prepare your N Time display."""

import argparse
import json
import os
import shutil
import sys
import time
import warnings
from getpass import GetPassWarning, getpass
from pathlib import Path
from tempfile import NamedTemporaryFile, mkdtemp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from device.board_config import SettingsError, load_board_config
from muni_board.api import ApiError, fetch_stop, parse_511_time
from muni_board.core import PayloadError, build_board, route_choices
from muni_board.render import render_human, terminal_text
from muni_board.settings import PROJECT_ROOT, load_settings


def prompt(label, default=""):
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip() or default
        if value:
            return value
        print("Enter a value to continue.")


def confirm(label):
    return input(f"{label} [y/N] ").strip().lower() in ("y", "yes")


def write_private_file(path, lines, replace):
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=".env-", delete=False
    ) as temp:
        temp_path = Path(temp.name)
        try:
            temp.writelines(lines)
            temp.close()
            if replace:
                os.replace(temp_path, path)
            else:
                os.link(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)


def secret(label):
    with warnings.catch_warnings():
        warnings.simplefilter("error", GetPassWarning)
        value = getpass(f"{label} (hidden): ")
    if not value.strip():
        raise SettingsError(f"Enter your {label}.")
    return value


def choose_route(routes):
    if routes:
        print("Routes reporting at this stop:")
        choices = list(routes)
        for number, (route, destinations) in enumerate(routes.items(), 1):
            description = f" toward {', '.join(destinations)}" if destinations else ""
            print(f"  {number}. Route {terminal_text(route + description)}")
        while True:
            answer = prompt("Choose a number, or enter M to type your route")
            if answer.lower() == "m":
                break
            if answer.isascii() and answer.isdecimal() and 1 <= int(answer) <= len(choices):
                return choices[int(answer) - 1]
            print("Choose one of the listed numbers or enter M.")
    else:
        print("511 has no routes to show for this stop right now.")
    return prompt("Enter the route shown on your transit map (for example, 38R)")


def setup_stops(path, replace):
    print("Request a 511 token at https://511.org/open-data/token")
    print("Look up your stops at https://511.org/travel/transit/stop-id")
    token = secret("511 API token").strip()
    values = {"TRANSIT_511_TOKEN": token}
    payloads = {}
    for number in (1, 2):
        print(f"\nDisplay row {number}")
        prefix = f"BOARD_ROW{number}_"
        agency = prompt("Transit agency code (SF for Muni)", "SF")
        stop_code = prompt("Stop ID from 511")
        values[prefix + "AGENCY"] = agency
        values[prefix + "STOP"] = stop_code
        try:
            payload = fetch_stop(token, agency, stop_code)
            routes = route_choices(payload)
        except (ApiError, PayloadError) as error:
            print(f"Could not check this stop. {terminal_text(str(error))}", file=sys.stderr)
            print("Check your 511 token, agency code, and stop ID, then run setup again.")
            return 1
        payloads[f"row{number}"] = payload
        values[prefix + "ROUTE"] = choose_route(routes)
        values[prefix + "LABEL"] = f"ROW{number}"

    route = values["BOARD_ROW1_ROUTE"].upper()
    values["BOARD_BADGE"] = (
        route if len(route) <= 2 and route.isascii() and route.isalnum() else "RT"
    )
    values["BOARD_TITLE"] = "TRANSIT"
    values["BOARD_POLL_SECONDS"] = "150"
    settings = load_board_config(values.get)
    for key, value in values.items():
        if not value.isprintable():
            raise SettingsError(f"{key} contains a control character. Check the value and try again.")
    lines = (f'{key}="{value}"\n' for key, value in values.items())
    write_private_file(path, lines, replace)
    print("\nSaved your two stops to .env.")
    board = build_board(payloads, settings, time.time(), parse_511_time)
    print(render_human(board))
    if any(not row["arrivals"] for row in board["directions"].values()):
        print("For a row with no arrivals, check the stop and route again during service.")
    print('\nOnce you have the hardware, see "Set up the display" in README.md.')
    return 0


def setup_board(path, replace, *, announce=True):
    settings = load_settings(PROJECT_ROOT / ".env")
    values = {
        "CIRCUITPY_WIFI_SSID": prompt("Your 2.4 GHz Wi-Fi network name"),
        "CIRCUITPY_WIFI_PASSWORD": secret("Wi-Fi password"),
        "TRANSIT_511_TOKEN": settings["token"],
        "BOARD_BADGE": settings["badge"],
        "BOARD_TITLE": settings["title"],
    }
    for number, stop in enumerate(settings["stops"], 1):
        prefix = f"BOARD_ROW{number}_"
        values[prefix + "AGENCY"] = stop["agency"]
        values[prefix + "STOP"] = stop["stop_code"]
        values[prefix + "ROUTE"] = stop["route"]
        values[prefix + "LABEL"] = stop["label"]
    lines = [f"{key} = {json.dumps(value, ensure_ascii=False)}\n" for key, value in values.items()]
    lines.append(f"BOARD_POLL_SECONDS = {settings['poll_seconds']}\n")
    write_private_file(path, lines, replace)
    if announce:
        print("Saved device/settings.toml. Drag it onto the CIRCUITPY drive.")
    return 0


BOARD_LIBRARIES = (
    "adafruit_bitmap_font", "adafruit_bus_device", "adafruit_display_text",
    "adafruit_esp32spi", "adafruit_connection_manager.mpy", "adafruit_requests.mpy",
    "adafruit_ticks.mpy",
)
BOARD_FILES = ("board_config.py", "board_layout.py", "diagnostics.py", "muni_logic.py", "code.py")


def prepare_board(bundle):
    library = bundle if bundle.name == "lib" else bundle / "lib"
    for name in BOARD_LIBRARIES:
        source = library / name
        present = source.is_file() if name.endswith(".mpy") else source.is_dir()
        if not present:
            raise SettingsError(f"Missing {name}. Choose the unzipped Adafruit .mpy bundle folder.")

    if not (PROJECT_ROOT / ".env").exists():
        result = setup_stops(PROJECT_ROOT / ".env", False)
        if result:
            return result

    output = Path(mkdtemp(prefix="N-Time-board-", dir=PROJECT_ROOT))
    try:
        (output / "lib").mkdir()
        for name in BOARD_LIBRARIES:
            source = library / name
            if source.is_dir():
                shutil.copytree(source, output / "lib" / name)
            else:
                shutil.copyfile(source, output / "lib" / name)
        for name in BOARD_FILES:
            shutil.copyfile(PROJECT_ROOT / "device" / name, output / name)
        setup_board(output / "settings.toml", False, announce=False)
    except BaseException:
        shutil.rmtree(output)
        raise
    print(f"Open {output}. Copy its contents to CIRCUITPY, copying code.py last.")
    print("This folder contains your Wi-Fi password and 511 token. Keep it private.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--prepare", metavar="BUNDLE", type=Path, help="assemble all board files from an unzipped Adafruit library bundle")
    mode.add_argument("--board", action="store_true", help="prepare the board's settings.toml")
    args = parser.parse_args(argv)
    relative_path = "device/settings.toml" if args.board else ".env"
    path = PROJECT_ROOT / relative_path
    replace = path.exists() or path.is_symlink()
    try:
        if args.prepare is not None:
            return prepare_board(args.prepare.expanduser())
        if replace and not confirm(f"{relative_path} already exists. Replace it?"):
            print(f"Kept your existing {relative_path}.")
            return 0
        if args.board:
            return setup_board(path, replace)
        return setup_stops(path, replace)
    except GetPassWarning:
        print("Run setup in an interactive terminal to enter secrets privately.", file=sys.stderr)
        return 2
    except (SettingsError, OSError, PayloadError) as error:
        print(f"Setup error: {error}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nSetup canceled.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
