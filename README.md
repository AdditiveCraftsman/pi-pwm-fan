# pi-pwm-fan

Temperature-controlled PWM fan for a Raspberry Pi 3B, using pigpio hardware PWM on GPIO 18. Includes an installer, two fan curves, and a live terminal dashboard (`fan-monitor.py`).

## Features

- Smooth temperature curve instead of simple on/off
- Hysteresis dead band (the speed only changes when the target moves by 5 percentage points or more), so the fan doesn't hunt up and down near a threshold
- Startup safety: fan runs at 100% for 5 seconds on boot
- Shutdown safety: fan goes to 100% if the service stops
- Logs every speed change to the systemd journal
- Two curves: **standard** (quiet) and **gaming** (aggressive, for RetroPie and other sustained loads)
- `fan-monitor.py`: real-time dashboard with temperature and fan-duty graphs

## Hardware

A basic 2-wire 5 V fan driven by a transistor, or a 4-wire PWM fan wired directly. Full parts list and wiring are in [HARDWARE.md](HARDWARE.md).

Transistor circuit used by this project:

| Connection | Goes to |
|---|---|
| GPIO 18 (header pin 12) | 1 kΩ resistor → transistor base |
| Fan positive (red) | 5 V (pin 2 or 4) |
| Fan negative (black) | Transistor collector |
| Transistor emitter | GND (e.g. pin 6) |
| 1N4007 flyback diode | Across the fan: cathode (banded end) to +5 V, anode to the collector |

> GPIO pins are 3.3 V logic. Never connect 5 V to a GPIO pin. Check your transistor's datasheet for which leg is the base, collector and emitter, because the order differs between 2N2222 packages.

## Fan curves

The fan is off at or below the first temperature and follows the table above it. Between rows the speed is interpolated linearly.

**Standard** (default)

| CPU temp | Fan speed |
|---|---|
| ≤ 45 °C | off |
| 45 °C | 20% |
| 50 °C | 25% |
| 55 °C | 50% |
| 60 °C | 70% |
| 65 °C | 85% |
| ≥ 70 °C | 100% |

**Gaming**

| CPU temp | Fan speed |
|---|---|
| ≤ 40 °C | off |
| 40 °C | 10% |
| 45 °C | 30% |
| 50 °C | 55% |
| 55 °C | 75% |
| 60 °C | 90% |
| ≥ 65 °C | 100% |

The standard curve starts at 20% rather than 0% because many small fans stall if they are asked to start below that.

## Install

Wire the fan first (see [HARDWARE.md](HARDWARE.md)), then:

```bash
git clone https://github.com/AdditiveCraftsman/pi-pwm-fan.git
cd pi-pwm-fan
sudo ./install-pwm-fan.sh --curve standard    # or: --curve gaming
```

The installer:

1. Installs `pigpiod` (from apt if available, otherwise builds it from source, which is needed on Kali)
2. Writes `/usr/local/bin/pwm-fan.py` with the chosen curve
3. Installs and starts the `pigpiod` and `pwm-fan` systemd services

To change the curve later, edit `TEMP_CURVE` in `/usr/local/bin/pwm-fan.py` and run `sudo systemctl restart pwm-fan`.

### Check it is working

```bash
sudo systemctl status pwm-fan
journalctl -u pwm-fan -f
```

You should see lines like `Temp 52.3 C -> fan 28%` whenever the speed changes.

## Live dashboard: `fan-monitor.py`

A terminal dashboard (Python standard library only) that shows CPU and GPU temperature, fan duty, CPU load, a curve-position bar and a log of recent fan changes.

```bash
python3 fan-monitor.py
```

| Key | Action |
|---|---|
| `F` | Toggle °C / °F |
| `Space` | Pause / resume |
| `q` | Quit |

How it works: it reads temperatures from the kernel and `vcgencmd`, and gets the fan duty by parsing the latest `fan NN%` lines of `journalctl -u pwm-fan`. Notes:

- The duty reading shows `--%` until the fan has changed speed at least once since boot, because that is when the service logs a line.
- Your user needs permission to read the journal (membership in the `systemd-journal` group, or run with `sudo`).
- The "Target" value and the curve bar read `TEMP_CURVE` from the installed `/usr/local/bin/pwm-fan.py`, so they always match the curve that is running (standard or gaming). If that file can't be read, it falls back to the standard curve.

## Known limitations

- **Analog 3.5 mm audio and hardware PWM conflict.** The Pi's analog audio jack uses the same PWM hardware, so you can't use the headphone jack and hardware PWM on GPIO 18 at the same time. Use HDMI, Bluetooth or USB audio on the fan Pi.
- Written and tested for the Raspberry Pi 3B. Other models use different PWM hardware and are untested.
- The temperature source is the CPU (`thermal_zone0`); the fan does not react to anything else.

## Files

| File | Purpose |
|---|---|
| `install-pwm-fan.sh` | One-command installer (`--curve standard\|gaming`) |
| `pwm-fan.py` | The fan controller (reference copy; the installer writes the deployed one) |
| `pwm-fan.service`, `pigpiod.service` | systemd units |
| `fan-monitor.py` | Terminal dashboard |
| `HARDWARE.md` | Parts, wiring and pin locations |

## Tested on

- Raspberry Pi 3B Rev 1.2
- Raspberry Pi OS (Bookworm / Trixie), RetroPie, and Kali Linux (Debian-based)
