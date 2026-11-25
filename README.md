# Transit Glow

A Wi-Fi connected 64×32 LED display for two Bay Area transit stops or routes,
powered by an Adafruit MatrixPortal M4 and the 511 SF Bay Stop Monitoring API.

![Photo of the N Judah LED arrival board on a wooden table with its power cord visible](docs/board-photo-wide.jpg)

The original board showing N Judah arrivals at the time of the photo.
[Data provided by 511.org](https://511.org).

The first number in each row is
the next arrival in minutes and seconds. The second is the following arrival
in whole minutes. `DUE` means less than a minute.

## Start here

You can try your own stops on a computer before buying the LED panel. Transit
Glow uses 511 SF Bay, so start with two Bay Area stops.

### Set up with a coding agent

Paste this into your coding agent, ChatGPT, or Claude. If it cannot open
GitHub, give it this README.

> Help me build Transit Glow for my stops using https://github.com/psatyajeet/transit-glow.
> Ask which computer I use and which Bay Area stops, routes, and directions I want.
> Help me find the stop IDs and get my own free 511 token. Walk me through
> running the setup script on my laptop, then show me the board preview so I
> can check both directions before buying anything. I’ll enter my token and
> Wi-Fi password privately in my own terminal.
>
> Once the preview looks right, use the shopping checklist to explain what I
> need. When I have the parts, guide me through installing CircuitPython and
> choosing the matching Adafruit library bundle. Use the setup script’s
> `--prepare` option to assemble the board folder. Show me what to copy onto
> `CIRCUITPY` and help me check the first arrivals. Give me one step at a time.

### Get your 511 token and stop IDs

1. Request a free 511 token. It works like a password for your requests. Agree
   to the terms on 511’s form and follow the email instructions.
   [Request a 511 token](https://511.org/open-data/token)
2. For each stop, choose the agency, route, direction, and stop in the lookup
   tool. Write down the number in the **Stop ID** box. Check the direction if
   your two stops share an intersection. [Look up a stop ID](https://511.org/travel/transit/stop-id)
3. For San Francisco Muni, the agency code is `SF`. For another agency, get
   its code from 511’s operator list. [511 agency lookup](https://511.org/open-data/faqs#where-do-i-find-transit-operator-ids)

### Try it on your computer

1. Install Python 3.11 or newer. On Windows, choose **Add Python to PATH** if
   the installer offers it. [Download Python](https://www.python.org/downloads/)
2. On the GitHub project page, choose **Code → Download ZIP** and unzip it.
3. Open a terminal in the unzipped folder. On a Mac, open Terminal, type
   `cd ` with a space, drag the folder into the window, and press Return.
   On Windows, open the folder in File Explorer, click the address bar, type
   `powershell`, and press Enter.
4. Run the setup command. On Windows, use `py -3 tools/setup.py`.

   ```sh
   python3 tools/setup.py
   ```

Paste your 511 token when the script asks. The terminal will keep it hidden
as you type. For each of your two rows, enter the stop ID and pick a route
from the list 511 returns. The script saves your choices and shows the next
arrivals. Compare those with your transit app during service. To see the two rows as they’ll appear in the terminal preview, run:

```sh
python3 -m muni_board --matrix
```

On Windows, use `py -3 -m muni_board --matrix`. Each row lists the minutes
until the next two arrivals. `DUE` means less than one minute.

If 511 has no route list, enter the route from your transit map and check
again during service. If the script shows a request error, check the token,
agency code, and stop ID. Rerun setup to correct a choice. It asks before
replacing your existing settings.

### Buy the parts

Get the **Adafruit Matrix Portal Starter Kit #4812**, a USB-C cable that
carries data, and a stand or mount. The kit includes the **MatrixPortal M4**,
64×32 LED panel, diffuser, and power supply. [Shopping checklist](SHOPPING_CHECKLIST.md)

## Set up the display

1. With power disconnected, plug the MatrixPortal M4 into the connector
   marked `IN` on the back of the LED panel. Remove any protective tape from
   the power screw posts. Attach red to `+5V` and black to `GND`, then plug
   the power lead into the panel. Put the panel on a nonconductive surface
   and power it with the kit’s 5 V supply. If the factory demo is still
   installed, check that its colors reach the whole panel.
   [Adafruit’s assembly photos](https://learn.adafruit.com/adafruit-matrixportal-m4/prep-the-matrixportal)
2. Connect the M4 to your computer with a USB-C data cable. Double-tap the
   board’s Reset button. Wait for a drive named `MATRIXBOOT`, then drag the
   MatrixPortal M4 `.uf2` file onto it. After the board restarts, the drive
   should be called `CIRCUITPY`. Look for that drive before copying any
   project files. The original prototype ran on CircuitPython 10.2.1.
   [MatrixPortal M4 download](https://circuitpython.org/board/matrixportal_m4/) ·
   [Adafruit’s reset and install photos](https://learn.adafruit.com/adafruit-matrixportal-m4/install-circuitpython)
3. Download Adafruit’s [CircuitPython library bundle](https://circuitpython.org/libraries)
   matching the first number of your CircuitPython version. Choose the **.mpy**
   bundle (for example, **10.x .mpy** for CircuitPython 10), then unzip it.
4. From the Transit Glow project folder, run the following command with the path
   to the unzipped bundle. On Windows, use `py -3` in place of `python3`.

   ```sh
   python3 tools/setup.py --prepare "/path/to/unzipped-bundle"
   ```

   On a Mac, you can type `python3 tools/setup.py --prepare ` and drag the
   unzipped folder into Terminal to fill in its path. The command reuses the
   stops you already checked, or walks you through choosing them. Enter your
   2.4 GHz Wi-Fi name and password when prompted.
5. Open the new `Transit-Glow-board-…` folder shown in the terminal. Copy its
   contents onto the root of `CIRCUITPY`, copying `code.py` last. The board
   starts automatically. Keep the generated folder private because its
   `settings.toml` contains your Wi-Fi password and 511 token.
6. Follow the [bench checklist](BUILD_CHECKLIST.md) to verify arrivals,
   Wi-Fi recovery, and standalone power before mounting it.

If the drive never appears, the board stays on `CONNECT`, or the display
keeps restarting, use the [troubleshooting checklist](BUILD_CHECKLIST.md#troubleshooting).
The original prototype used AirLift 3.3.0 for its Wi-Fi chip. AirLift and
CircuitPython are separate firmware updates.

<details>
<summary>Manual setup, troubleshooting, and polling limits</summary>

Copy `.env.example` to `.env` and fill in the token, agency codes, stop IDs,
and routes. Match route IDs to the case-sensitive `LineRef` returned by 511.
Row labels support up to four letters, digits, spaces, or hyphens. The header
has a two-character badge and an eight-character title. The device template
is available at `device/settings.toml.example`.

For troubleshooting, `python3 -m muni_board --save-raw var/511` saves the
responses locally as `row1.json` and `row2.json`. Look for
`MonitoredVehicleJourney.LineRef`, `DirectionRef`, and `DestinationName`.
Use `--matrix` for a text preview, `--json` for the board model, or
`--watch` for repeated refreshes. Run
`python3 -m unittest discover -s tests -v` for offline tests.

One display uses two requests every 150 seconds, or about 48 per hour.
The default limit is 60 per hour per token. Stop any laptop watch loop
before starting a board on the same token. If 511 has approved an increased
quota, set `BOARD_POLL_SECONDS` as low as 30 in `.env` before generating board
settings. At 30 seconds, two stops use about 240 requests per hour. A quota
of 300 per hour leaves room for setup and occasional other calls. For an
already installed board, update `board_config.py` on `CIRCUITPY` before
changing the interval. [511 API limits](https://511.org/open-data/transit)

</details>

The optional firmware preview uses the [Terminus bitmap font shipped with CircuitPython](https://github.com/adafruit/circuitpython/blob/10.2.1/tools/fonts/ter-u12n.bdf).
