# Hardware guide

This project controls a fan with PWM on GPIO 18 (header pin 12). You have two options for the hardware side.

## Option A: Transistor circuit (what this project uses)

Use this if you have a basic 2-wire 5 V fan (power and ground only, no signal wire).

### Parts list

| Part | Purpose | Cost |
|------|---------|------|
| 2N2222 NPN transistor | Switches fan power on and off rapidly (PWM) | ~$0.50 |
| 1 kΩ resistor | Limits current from the GPIO pin into the transistor base | ~$0.10 |
| 1N4007 diode | Absorbs the voltage spike when the fan turns off (flyback protection) | ~$0.10 |
| Female-to-male dupont wires | Connect the GPIO header to your breadboard or perfboard | ~$3 for a 40-pack |
| Any 5 V 2-wire fan | The fan being controlled | varies |

The 2N2222 handles typical Pi fans comfortably. A 2N3904 or BC547 only suits small fans drawing under about 100 mA. For higher-current fans, use a logic-level N-channel MOSFET such as the IRLZ44N instead.

### Wiring

```
 +5V (pin 2 or 4) ──┬───────────────────┐
                    │                   │
              Fan red (+)        1N4007 cathode (banded end)
                    │                   │
                 [ FAN ]             [ DIODE ]
                    │                   │
             Fan black (−)       1N4007 anode
                    │                   │
                    └─────────┬─────────┘
                              │
                        Collector (C)

 GPIO 18 (pin 12) ──[ 1 kΩ ]── Base (B)
 GND (pin 6) ───────────────── Emitter (E)
```

| From | To |
|------|----|
| Pi pin 12 (GPIO 18) | One end of the 1 kΩ resistor |
| Other end of the resistor | Transistor base |
| Pi pin 2 or 4 (5 V) | Fan red wire, and the diode's banded end (cathode) |
| Fan black wire | Transistor collector, and the diode's other end (anode) |
| Transistor emitter | Pi pin 6 (GND) |

**Check your transistor's pinout.** The order of emitter, base and collector differs between 2N2222 packages (for example PN2222 in a plastic TO-92 case versus a metal can). Always confirm against the datasheet for the exact part you have. Before plugging anything in, you can check the header with a multimeter: pin 4 to pin 6 should read about 5 V.

### How it works

1. GPIO 18 sends a PWM signal (a 250 Hz square wave whose duty cycle is 0 to 100%).
2. The 1 kΩ resistor limits current into the transistor base to roughly 2.6 mA.
3. While the base is driven, the transistor lets current flow from collector to emitter.
4. That completes the circuit 5 V → fan → collector → emitter → GND.
5. The fan's average speed follows the duty cycle.
6. The flyback diode protects the transistor from the voltage spike when the fan's motor coil is switched off.

### Important notes

- **GPIO pins are 3.3 V logic.** Never connect 5 V directly to any GPIO pin.
- **The fan runs from the 5 V rail**, not from GPIO. GPIO only drives the transistor.
- **The flyback diode is not optional.** Without it, inductive kickback from the fan motor can damage the transistor or the Pi.
- **Don't put the fan wire on the pins next to 5 V by accident.** Count pins from pin 1 (nearest the SD card slot): odd pins are the inner row, even pins the outer row.
- **Thermal paste** fills air gaps between heatsink and chip. It is not adhesive, so heatsinks need mechanical retention (a clip, tape or a press-fit case).

## Option B: Buy a PWM-capable fan (no circuit needed)

If you don't want to build a transistor circuit, buy a fan with a built-in PWM signal wire. It connects straight to the Pi: no transistor, resistor or diode.

### What to look for

- **5 V fan** (not 12 V; the Pi only provides 5 V)
- **4-wire** (the extra wire is the PWM control input)
- **30 mm or 40 mm** (fits Pi 3B cases)

### Example fans

| Fan | Voltage | Size | Control | Notes |
|-----|---------|------|---------|-------|
| Noctua NF-A4x10 5V PWM | 5 V | 40 mm | 4-wire PWM | Very quiet, around $15 |
| GeeekPi Pi fan | 5 V | 30 mm | 3-wire | Cheap, designed for the Pi, noisier |
| Argon MINI fan | 5 V | 30 mm | PWM | Comes with some Argon cases |

Check the exact model's datasheet before buying. Specs and pin colors vary.

### Wiring (4-wire PWM fan)

| Fan wire | Pi connection |
|----------|---------------|
| +5 V | Pin 2 or 4 |
| GND | Pin 6 |
| PWM control | Pin 12 (GPIO 18) |
| Tachometer (RPM) | Not used |

**Change the PWM frequency.** 4-wire fans normally expect a PWM signal around 25 kHz, while this project's script runs at 250 Hz, which suits the transistor circuit. For a 4-wire fan, set `PWM_FREQ = 25000` in `/usr/local/bin/pwm-fan.py` and restart the service (`sudo systemctl restart pwm-fan`). Confirm the recommended frequency and the control pin's voltage tolerance in your fan's datasheet.

### 3-wire fans

A 3-wire fan with only power, ground and tachometer (no PWM input) still needs the transistor circuit from Option A. The third wire is RPM feedback, not speed control.

## GPIO 18 pin location

Looking at the Pi with the header at the top right and the SD card slot at the far end, pin 1 is the corner nearest the SD card slot. Even pins are the outer row (nearest the board edge) and odd pins are the inner row.

```
          3V3  (1)  (2)  5V      <- pin 2: 5 V power
   GPIO2 (SDA)  (3)  (4)  5V      <- pin 4: 5 V power
   GPIO3 (SCL)  (5)  (6)  GND     <- pin 6: ground
         GPIO4  (7)  (8)  GPIO14
           GND  (9)  (10) GPIO15
        GPIO17 (11)  (12) GPIO18  <- pin 12: PWM signal
        GPIO27 (13)  (14) GND
        GPIO22 (15)  (16) GPIO23
           3V3 (17)  (18) GPIO24
        GPIO10 (19)  (20) GND
         GPIO9 (21)  (22) GPIO25
        GPIO11 (23)  (24) GPIO8
           GND (25)  (26) GPIO7
```

### Audio jack conflict

The Pi's analog 3.5 mm audio output uses the same PWM hardware as hardware PWM on GPIO 18. You can't use both at once, so use HDMI, Bluetooth or USB audio on the Pi that drives the fan.

## After the hardware is connected

Run the installer:

```bash
git clone https://github.com/AdditiveCraftsman/pi-pwm-fan.git
cd pi-pwm-fan
sudo ./install-pwm-fan.sh --curve standard   # or --curve gaming
```
