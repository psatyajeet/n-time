"""CircuitPython firmware for the MatrixPortal M4 transit board."""

import gc
import os
import time

import adafruit_connection_manager
import adafruit_requests
import board
import busio
import displayio
import framebufferio
import microcontroller
import rgbmatrix
import terminalio
from adafruit_display_text.label import Label
from adafruit_esp32spi import adafruit_esp32spi
from board_config import SettingsError, load_board_config, query_value
from board_layout import LABEL_LAYOUT, ROW_LAYOUT, draw_small, follow_x
from diagnostics import boot as diagnostics_boot
from diagnostics import record as diagnostics_record
from digitalio import DigitalInOut
from fontio import Glyph
from muni_logic import arrival_pair_texts, parse_remaining_seconds
from watchdog import WatchDogMode

API_URL = "https://api.511.org/transit/StopMonitoring"
STALE_SECONDS = 600
EXPIRED_SECONDS = 1800
REQUEST_TIMEOUT = 5  # The HTTP library tries twice, so two waits must fit in the watchdog window.
WATCHDOG_TIMEOUT = 16

class CountdownFont:
    def get_bounding_box(self):
        return terminalio.FONT.get_bounding_box()

    def get_glyph(self, codepoint):
        glyph = terminalio.FONT.get_glyph(codepoint)
        if glyph is None or codepoint != ord(":"):
            return glyph
        # Keep the existing glyph, with two fewer pixels on each side of the colon.
        return Glyph(
            glyph.bitmap,
            glyph.tile_index,
            glyph.width,
            glyph.height,
            glyph.dx - 2,
            glyph.dy,
            glyph.shift_x - 4,
            glyph.shift_y,
        )


def make_display(config):
    displayio.release_displays()
    matrix = rgbmatrix.RGBMatrix(
        width=64,
        height=32,
        bit_depth=3,
        rgb_pins=(
            board.MTX_R1,
            board.MTX_G1,
            board.MTX_B1,
            board.MTX_R2,
            board.MTX_G2,
            board.MTX_B2,
        ),
        addr_pins=(board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC, board.MTX_ADDRD),
        clock_pin=board.MTX_CLK,
        latch_pin=board.MTX_LAT,
        output_enable_pin=board.MTX_OE,
    )
    display = framebufferio.FramebufferDisplay(matrix, auto_refresh=True)
    group = displayio.Group()
    countdown_font = CountdownFont()
    labels = {}
    for name, (x, y, color) in LABEL_LAYOUT.items():
        font = countdown_font if name.endswith("_next") else terminalio.FONT
        text = config["badge"] if name == "route" else ""
        labels[name] = Label(font, text=text, color=color, x=x, y=y)
        group.append(labels[name])

    for row, (x, y, color) in zip(config["stops"], ROW_LAYOUT):
        palette = displayio.Palette(2)
        palette.make_transparent(0)
        palette[1] = color
        bitmap = displayio.Bitmap(15, 7, 2)
        draw_small(bitmap, row["label"])
        group.append(displayio.TileGrid(bitmap, pixel_shader=palette, x=x, y=y))
    display.root_group = group
    return display, labels


DISPLAY = None
LABELS = None
WATCHDOG_ACTIVE = False
LAST_LABEL_TEXT = {}


def start_watchdog():
    global WATCHDOG_ACTIVE
    try:
        microcontroller.watchdog.timeout = WATCHDOG_TIMEOUT
        microcontroller.watchdog.mode = WatchDogMode.RESET
        microcontroller.watchdog.feed()
        WATCHDOG_ACTIVE = True
        print("MUNI watchdog_started timeout=" + str(WATCHDOG_TIMEOUT))
        diagnostics_record("watchdog_started", timeout=WATCHDOG_TIMEOUT)
    except Exception as error:
        WATCHDOG_ACTIVE = False
        print("Watchdog unavailable: " + type(error).__name__)
        diagnostics_record("watchdog_unavailable", error=type(error).__name__)


def feed_watchdog():
    if WATCHDOG_ACTIVE:
        microcontroller.watchdog.feed()


def sleep_with_watchdog(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        feed_watchdog()
        remaining = deadline - time.monotonic()
        # The deadline can pass between the two clock reads.
        time.sleep(max(0, min(1, remaining)))


def set_label_text(name, value):
    if LAST_LABEL_TEXT.get(name) == value:
        return
    if name.endswith("_follow"):
        LABELS[name].x = follow_x(value)
    LABELS[name].text = value
    LAST_LABEL_TEXT[name] = value


def show(inbound=("", ""), outbound=("", ""), *, title):
    set_label_text("title", title)
    set_label_text("in_next", inbound[0])
    set_label_text("in_follow", inbound[1])
    set_label_text("out_next", outbound[0])
    set_label_text("out_follow", outbound[1])


def require_settings():
    names = ("CIRCUITPY_WIFI_SSID", "CIRCUITPY_WIFI_PASSWORD", "TRANSIT_511_TOKEN")
    values = [os.getenv(name) for name in names]
    missing = [name for name, value in zip(names, values) if not value]
    if missing:
        raise SettingsError("Missing settings: " + ", ".join(missing))
    return values


def make_network(ssid, password):
    spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
    esp = adafruit_esp32spi.ESP_SPIcontrol(
        spi,
        DigitalInOut(board.ESP_CS),
        DigitalInOut(board.ESP_BUSY),
        DigitalInOut(board.ESP_RESET),
    )
    pool = adafruit_connection_manager.get_radio_socketpool(esp)
    ssl_context = adafruit_connection_manager.get_radio_ssl_context(esp)
    return esp, adafruit_requests.Session(pool, ssl_context)


def connect_with_retry(esp, ssid, password):
    while not esp.is_connected:
        show(title="CONNECT")
        feed_watchdog()
        print("MUNI wifi_connect_start")
        try:
            esp.connect_AP(ssid, password)
            print("MUNI wifi_connect_ok")
            diagnostics_record("wifi_connected")
        except Exception as error:  # Keep a useful message on the physical board.
            print("Wi-Fi connection failed: " + type(error).__name__)
            diagnostics_record("wifi_connect_failed", error=type(error).__name__)
            show(title="WIFI!")
            sleep_with_watchdog(15)


def fetch_stop(session, token, stop):
    stop_code = stop["stop_code"]
    print("MUNI fetch_start stop=" + stop_code)
    url = (
        API_URL
        + "?api_key="
        + query_value(token)
        + "&agency="
        + query_value(stop["agency"])
        + "&stopCode="
        + query_value(stop_code)
        + "&format=json"
    )
    response = session.get(
        url,
        headers={"Accept-Encoding": "identity"},
        timeout=REQUEST_TIMEOUT,
    )
    try:
        if response.status_code != 200:
            raise RuntimeError("HTTP " + str(response.status_code))
        result = parse_remaining_seconds(response.json(), stop["route"])
        print("MUNI fetch_ok stop=" + stop_code + " arrivals=" + str(len(result)))
        return result
    finally:
        response.close()


def render(config, cache, fetched_at, now, has_error):
    rows = []
    stale = False
    for row in config["stops"]:
        key = row["key"]
        age = now - fetched_at[key] if fetched_at[key] is not None else EXPIRED_SECONDS + 1
        if age > EXPIRED_SECONDS:
            value = ("NO DATA", "")
        else:
            value = arrival_pair_texts(cache[key], age)
            stale = stale or age > STALE_SECONDS
        rows.append(value)

    title = config["title"]
    if has_error:
        title = "STALE" if stale else "API ERR"
    show(rows[0], rows[1], title=title)


def run():
    global DISPLAY, LABELS, LAST_LABEL_TEXT
    LAST_LABEL_TEXT = {}
    try:
        config = load_board_config(os.getenv)
        ssid, password, token = require_settings()
    except SettingsError as error:
        DISPLAY, LABELS = make_display({"badge": "", "stops": ()})
        show(title="SETUP")
        print(str(error))
        while True:
            time.sleep(60)

    DISPLAY, LABELS = make_display(config)
    start_watchdog()
    esp, session = make_network(ssid, password)
    connect_with_retry(esp, ssid, password)
    cache = {row["key"]: [] for row in config["stops"]}
    fetched_at = {row["key"]: None for row in config["stops"]}
    next_fetch = 0
    next_gc = 0
    had_error = False
    last_success = time.monotonic()

    while True:
        feed_watchdog()
        now = time.monotonic()
        if now >= next_fetch:
            had_error = False
            print("MUNI cycle_start")
            if not esp.is_connected:
                try:
                    feed_watchdog()
                    esp.connect_AP(ssid, password)
                except Exception as error:  # CircuitPython reports driver-specific exceptions.
                    had_error = True
                    print("Wi-Fi reconnect failed: " + type(error).__name__)
                    diagnostics_record("wifi_reconnect_failed", error=type(error).__name__)
                if not esp.is_connected:
                    had_error = True

            if esp.is_connected:
                for row in config["stops"]:
                    key = row["key"]
                    try:
                        feed_watchdog()
                        cache[key] = fetch_stop(session, token, row)
                        fetched_at[key] = last_success = time.monotonic()
                        feed_watchdog()
                    except Exception as error:  # Preserve cached data on transient failures.
                        had_error = True
                        print(key + " fetch failed: " + type(error).__name__)
                        diagnostics_record("fetch_failed", stop=key, error=type(error).__name__)
                    gc.collect()

            # Every cached value has expired, so a restart loses nothing and clears stuck sockets.
            if time.monotonic() - last_success > EXPIRED_SECONDS:
                diagnostics_record("no_data_restart")
                raise RuntimeError("no successful fetch")

            next_fetch = time.monotonic() + config["poll_seconds"]

        render(config, cache, fetched_at, time.monotonic(), had_error)
        if now >= next_gc:
            gc.collect()
            next_gc = now + 30
        sleep_with_watchdog(1)


def restart_after_error(error):
    gc.collect()
    print("Fatal firmware error: " + type(error).__name__)
    diagnostics_record("fatal_error", error=type(error).__name__)
    try:
        show(("ERROR", ""), ("RESET", ""), title="ERROR")
    except Exception:
        pass
    sleep_with_watchdog(3)
    microcontroller.reset()


if __name__ == "__main__":
    while True:
        try:
            diagnostics_boot()
            run()
        except Exception as error:
            restart_after_error(error)
