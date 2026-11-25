# Transit Glow

## Set up with a coding agent

> Help me build https://github.com/psatyajeet/transit-glow. Ask what computer I use and which two Bay Area stops and directions I want. Help me preview live arrivals before I buy parts. Then walk me through the hardware setup one step at a time. I’ll enter my 511 token and Wi-Fi password in my own terminal.

![N Judah LED board showing the next two trains in each direction](docs/board-photo-wide.jpg)

Data provided by [511.org](https://511.org).

## Preview your stops

Get a [free 511 token](https://511.org/open-data/token) and [look up your two stop IDs](https://511.org/travel/transit/stop-id). Use `SF` for Muni.

[Download the project](https://github.com/psatyajeet/transit-glow/archive/refs/heads/main.zip), unzip it, and run these commands in the project folder with Python 3.11 or newer. On Windows, use `py -3` for `python3`.

```sh
python3 tools/setup.py
python3 -m muni_board --matrix
```

## Set up the display

1. Assemble the MatrixPortal M4 and LED panel with the power disconnected. [Parts list](SHOPPING_CHECKLIST.md) · [Assembly photos](https://learn.adafruit.com/adafruit-matrixportal-m4/prep-the-matrixportal)
2. Connect a USB-C data cable, double-tap Reset, and copy the [MatrixPortal M4 firmware](https://circuitpython.org/board/matrixportal_m4/) (`.uf2`) to `MATRIXBOOT`. It restarts as `CIRCUITPY`.
3. Unzip the [Adafruit .mpy bundle](https://circuitpython.org/libraries) for your CircuitPython major version. Run this with the bundle folder’s path:

   ```sh
   python3 tools/setup.py --prepare "/path/to/unzipped-bundle"
   ```

4. Enter your 2.4 GHz Wi-Fi details. Copy the generated folder’s **contents** to `CIRCUITPY`, with `code.py` last. Keep the folder private. It contains your credentials.

[Board checks and troubleshooting](BUILD_CHECKLIST.md)
