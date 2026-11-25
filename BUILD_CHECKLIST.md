# Bench checklist

## Computer

- [ ] Confirm both stops and route IDs against live 511 data during service.
- [ ] Stop the laptop's watch loop before starting the board with the same key.

## MatrixPortal M4

- [ ] Bench test on a nonconductive surface. Disconnect power before mating
      or disconnecting the HUB75 panel or changing the power leads.
- [ ] Confirm the demo lights the full panel.
- [ ] Install CircuitPython and its matching libraries, local settings, and firmware.
- [ ] Check both directions and the next two arrivals against a trusted live source.
- [ ] Watch the first countdown tick down. Check that it changes to `DUE`
      near arrival and advances to the next prediction.
- [ ] Interrupt Wi-Fi after a successful fetch. Confirm cached countdowns
      continue. Restore Wi-Fi and verify that fresh arrivals return on a later poll.
- [ ] Power cycle the board using the kit's power supply and confirm that live
      arrivals return without a computer connected.
- [ ] Let it run for a day before committing to an enclosure. Check temperatures,
      ventilation, cable strain relief, and readability from the normal viewing distance.

## Troubleshooting

| What you see | What to check |
| --- | --- |
| Neither `MATRIXBOOT` nor `CIRCUITPY` appears | Try a known USB data cable directly in another port, then double-tap Reset. On a factory-programmed board, the demo may run before a drive appears. [USB and bootloader steps](https://learn.adafruit.com/adafruit-matrixportal-m4/install-circuitpython) |
| `MATRIXBOOT` appears but `CIRCUITPY` does not | Copy the `.uf2` specifically for **MatrixPortal M4** to `MATRIXBOOT`. Give it time to restart and remount. If user code or a read-only drive is blocking an existing installation, follow Adafruit's safe mode instructions. [CircuitPython troubleshooting](https://learn.adafruit.com/welcome-to-circuitpython/troubleshooting) |
| Blank panel or a missing-library message | First check the kit power supply and panel `IN` connector with power off. If USB still works, open the serial console. A missing module or incompatible `.mpy` usually means a library is absent or the library bundle does not match the CircuitPython major version. [Serial console guide](https://learn.adafruit.com/welcome-to-circuitpython/kattni-connecting-to-the-serial-console) |
| `SETUP` | Check that the generated file is named exactly `settings.toml` and sits directly on `CIRCUITPY`. The USB serial console names missing or invalid settings. |
| `CONNECT` or `WIFI!` persists | Check that the network is 2.4 GHz and that its name and password in `settings.toml` are correct. If that checks out, test the M4's AirLift Wi-Fi separately with Adafruit's example. If the example fails too, check the separate ESP32 firmware. The original prototype ran on AirLift 3.3.0. Back up the board files locally before using the updater, then restore your Transit Glow files if the update example replaced them. [Wi-Fi example](https://learn.adafruit.com/adafruit-matrixportal-m4/internet-connect) · [AirLift firmware update](https://learn.adafruit.com/adafruit-matrixportal-m4/updating-esp32-firmware) |
| `API ERR`, `STALE`, or `NO DATA` | `API ERR` means the last update failed for at least one row. `STALE` means a row is more than 10 minutes old. `NO DATA` means a row is more than 30 minutes old or never loaded. After 30 minutes with no successful update, the board restarts at its next update attempt. Run a one-time arrival check on the computer with the same settings. Confirm the token, stop and route, and stop any laptop watch loop using the same key. |
| Board keeps rebooting or goes dark | Test with the kit's power supply and check that the power leads and USB-C plug are firmly seated. Capture the USB serial output and look for the last message before the reset and the next boot message. `BROWNOUT` points toward power. `WATCHDOG` means the board reset after code stopped responding. |

For resets that are hard to reproduce, keep the USB serial console open while
testing. On macOS or Linux,
`python3 tools/capture_serial.py --device YOUR_SERIAL_PORT` also writes a
timestamped copy to `var/serial.log`. Use the serial port shown by your own
computer and close other programs using that port first.

Once the panel runs reliably, fit the diffuser and stand or enclosure. Leave
room for ventilation and the USB-C plug, keep the power brick outside the
enclosure, and put a small **Data provided by 511.org** credit near the panel.
[Adafruit's diffuser guide](https://learn.adafruit.com/adafruit-matrixportal-m4/led-matrix-diffuser)
