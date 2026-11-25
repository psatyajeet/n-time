# N Time

A 64×32 LED board that shows the next two arrivals at two Bay Area transit stops.

![N Judah LED board showing the next two trains in each direction](docs/board-photo-wide.jpg)

Data provided by [511.org](https://511.org).

## Set up with a coding agent

```text
Help me build https://github.com/psatyajeet/n-time. Ask what
computer I use and which two Bay Area stops and directions I want.
Help me preview live arrivals before I buy parts. Then walk me
through the hardware setup one step at a time. I'll enter my 511
token and Wi-Fi password in my own terminal.
```

## Preview your stops

Get a [free 511 token](https://511.org/open-data/token) and [look up your two stop IDs](https://511.org/travel/transit/stop-id). Choose the direction for each stop. Opposite sides of the same street can have different IDs. Use `SF` for Muni.

[Download the project](https://github.com/psatyajeet/n-time/archive/refs/heads/main.zip), unzip it, and open the folder containing this README. On Mac, type `cd ` (with a space) in Terminal, drag that folder into the window, and press Return. On Windows, type `powershell` in the folder's address bar and press Enter.

Run these commands one at a time with [Python 3.11 or newer](https://www.python.org/downloads/). On Windows, use `py -3` for `python3`.

```sh
python3 tools/setup.py
python3 -m muni_board --matrix
```

Setup asks for your token (the characters stay hidden), then lets you pick a route for each stop. The preview shows the minutes until the next two arrivals in each row.

Setup names the rows `ROW1` and `ROW2`. To change the text on the display, edit `.env` before preparing the board:

| Setting | Length | Example |
| --- | --- | --- |
| `BOARD_BADGE` | 1 to 2 characters | `N` |
| `BOARD_TITLE` | 1 to 8 characters | `JUDAH` |
| `BOARD_ROW1_LABEL`, `BOARD_ROW2_LABEL` | 1 to 4 characters | `EAST`, `WEST` |

## Set up the display

1. Assemble the MatrixPortal M4 and LED panel with the power disconnected. [Parts list](SHOPPING_CHECKLIST.md) · [Assembly photos](https://learn.adafruit.com/adafruit-matrixportal-m4/prep-the-matrixportal)
2. Plug the MatrixPortal into your computer with a USB-C cable that supports data. Press and release the small **Reset** button on the MatrixPortal twice quickly, like double-clicking a mouse. Its light should turn green. Look for a new drive called `MATRIXBOOT` in Finder (Mac) or File Explorer (Windows). [Photo showing the Reset button](https://learn.adafruit.com/adafruit-matrixportal-m4/install-circuitpython)
3. Download the [CircuitPython .uf2 file for the MatrixPortal M4](https://circuitpython.org/board/matrixportal_m4/) and drag it onto `MATRIXBOOT`. Wait for the board to restart. When a drive called `CIRCUITPY` appears, the installation is complete.
4. Download and unzip the [Adafruit .mpy library bundle](https://circuitpython.org/libraries) that matches the first number of your CircuitPython version (for example, **10.x .mpy** for 10.2.1). In your project terminal, replace the quoted example path below with the path to the unzipped folder containing `lib`.

   ```sh
   python3 tools/setup.py --prepare "/path/to/unzipped-bundle"
   ```

5. Enter your 2.4 GHz Wi-Fi name and password when prompted. Open the `N-Time-board-…` folder printed in the terminal. Open `CIRCUITPY` in a second window. Copy everything inside the generated folder except `code.py` directly into that drive, then copy `code.py` last. This starts the display. Keep the generated folder private because `settings.toml` holds your Wi-Fi password and 511 token.

[Board checks and troubleshooting](BUILD_CHECKLIST.md)
