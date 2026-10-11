# cell-firmware

Arduino Uno sketch for the one-cell Braille display: six SG90 servos, one per
dot. The Uno holds the Braille table and the letter timing. The Jetson, or
anything with a serial port, sends a word such as `SPELL chair` and the board
spells it: raise the letter's dots, hold, lower, short gap, next letter.

```
Jetson ── USB serial ──▶ Arduino Uno ── D2..D7 ──▶ six SG90s ──▶ dots 1..6
  "SPELL chair"            Braille table, timing,
  ◀── "CELL 09 c" ...      servo endpoints (EEPROM)
```

**Status.** The sketch compiles for the Uno (about 29% of flash and 45% of
RAM). The logic passes host tests and runs in a simulator. It has not yet
been run on a real board with servos; the endpoint defaults are starting points
until each dot is calibrated.

## Files

```text
magneto_cell/magneto_cell.ino   Arduino glue: servos, serial port, EEPROM
magneto_cell/cell_core.*        All the logic, plain C++ (also built on a computer)
servo_test/servo_test.ino       Standalone movement test for the six servos
test/test_core.cpp              Host tests: make test
sim/cell_sim.cpp                The firmware on stdin/stdout: make sim
```

## Wiring

Dots as the reader sees them from above:

```
1  4
2  5
3  6
```

| Arduino | Connects to                            |
| ------- | -------------------------------------- |
| D2      | dot 1 servo signal                     |
| D3      | dot 2 servo signal                     |
| D4      | dot 3 servo signal                     |
| D5      | dot 4 servo signal                     |
| D6      | dot 5 servo signal                     |
| D7      | dot 6 servo signal                     |
| GND     | servo supply negative (common ground)  |
| USB     | Jetson: data and the Arduino's own power |

- Servo supply positive goes to all six servo red leads. Servo supply negative
  goes to all six servo grounds **and** to Arduino GND.
- Do not power the servos from the Arduino's 5 V pin, from the Jetson, or
  through breadboard power rails. A breadboard can carry the signal wires.
- SG90 leads are usually brown = ground, red = positive, orange = signal.
  Check yours.
- The supply (for example a four-cell NiMH pack) is still undecided. Check
  that the servos accept its fully charged voltage, and that it can supply six
  servos starting at once.

## Servo test first

`servo_test/servo_test.ino` checks the wiring and power before the real
firmware goes on. It uses the same pins, needs no calibration, and does no
Braille.

1. Flash it (same steps as below, with `servo_test` in place of
   `magneto_cell`). Open the Serial Monitor at 115200 baud.
2. It moves each servo to CENTER (1500 µs) one at a time. It then loops: each
   servo in turn swings LOW → HIGH → LOW (1300 ↔ 1700 µs, about 40°), then all
   six swing together twice. The monitor prints which dot and pin should be
   moving, so a swapped wire shows up straight away.
3. Keys: `1`–`6` wiggle one servo, `a` all HIGH, `z` all LOW, `c` all CENTER,
   `r` resume the loop.

What to look for:

- **A servo doesn't move.** Check its signal pin, then its power and ground.
- **The wrong servo moves.** The signal wires are swapped.
- **Jitter or buzzing at rest.** The supply is weak or the ground is not shared.
- **"servo test starting" reappears by itself, usually during "all together".**
  The board reset because the servos pulled the supply down.

The swing is a fixed 40° around 1500 µs. It only checks wiring and power; the
real UP/DOWN positions are in `magneto_cell` (see below).

## Flash

Arduino IDE: open `magneto_cell/magneto_cell.ino`, choose **Arduino Uno**, and
upload. The Servo library ships with the IDE.

arduino-cli:

```bash
arduino-cli core install arduino:avr
arduino-cli lib install Servo
arduino-cli compile --fqbn arduino:avr:uno cell-firmware/magneto_cell
arduino-cli upload  --fqbn arduino:avr:uno -p /dev/ttyACM0 cell-firmware/magneto_cell
```

## Default positions

The horns stay where they were fitted. The firmware turns each one to its
extended (dot up) and rest (dot down) angle. Set them in degrees at the top of
`magneto_cell/cell_core.h`:

```cpp
const int16_t EXTENDED_ANGLE_DEG = -15;  // dot UP (pressed, red line)
const int16_t REST_ANGLE_DEG = 32;       // dot DOWN (rest, blue line)
const int8_t LEFT_BANK_DIR = 1;          // dots 1-3
const int8_t RIGHT_BANK_DIR = -1;        // dots 4-6
const uint16_t US_PER_10_DEG = 105;      // SG90: about 10.5 us per degree
```

- Angles are measured from where the horn sits at 1500 µs. Positive turns one
  way, negative the other.
- Dots 4–6 are a mirror image, so `RIGHT_BANK_DIR = -1` turns them the
  opposite way. If a whole bank moves backwards, flip its `*_BANK_DIR`.
- Re-flash after editing. The new angles replace any endpoints saved with
  `SAVE`, so there's no need to send `DEFAULTS`.

With the values above, the pulses are:

| Dots | UP (extended) | DOWN (rest) |
|------|---------------|-------------|
| 1–3 | 1343 | 1836 |
| 4–6 | 1657 | 1164 |

## Check and fine-tune each dot

Flash `magneto_cell` and open the Serial Monitor at **115200 baud** with line
ending **Newline**.

1. `DOTS 123456` should raise every dot; `DOTS` lowers them.
2. **A bank moves backwards** (pressed and rest are swapped): flip that bank's
   `LEFT_BANK_DIR` or `RIGHT_BANK_DIR` in `cell_core.h` and re-flash.
3. **All arms are a little off:** change the two angles and re-flash.
   **Only one is off:** nudge it with `JOG` in 20–30 µs steps (e.g. `JOG 2 1320`,
   `JOG 2 1360`), then store it with `CAL 2 <up> <down>` and `SAVE`.
4. `DOTS 123456` and `SPELL hello` to check, then `SAVE`. `CONFIG` prints the
   settings as commands you can paste back later.

## Commands

One command per line. Command words are not case sensitive.

| Command                               | Does                                                              |
| ------------------------------------- | ----------------------------------------------------------------- |
| `SPELL text` (or `S text`)            | Spells the letters a–z; spaces give a word gap; other characters are skipped. Interrupts the current word. |
| `DOTS 125`                            | Shows a raw pattern and holds it; `DOTS` alone lowers every dot     |
| `CLEAR` (or `C`)                      | Stops spelling and lowers every dot                               |
| `TIMING hold gap word [stagger]`      | Milliseconds: letter hold, gap between letters, gap between words, and the delay between individual servo moves |
| `CAL dot up_us down_us`               | Sets a dot's endpoints (500–2500 µs) and applies them at once      |
| `JOG dot pulse_us`                    | Moves one servo directly, for calibration, until the next pattern  |
| `CONFIG`                              | Prints the current settings as `CAL`/`TIMING` lines               |
| `SAVE` / `DEFAULTS`                   | Writes the settings to EEPROM / restores the defaults (not saved)  |
| `PING`, `HELP`                        | `PONG magneto-cell 1` / the command list                          |

The defaults are a 3000 ms letter hold, 300 ms gap, 1000 ms word gap and 20 ms
servo stagger. Changes last until reset unless saved.

## Messages from the board

| Line                     | Meaning                                                        |
| ------------------------ | -------------------------------------------------------------- |
| `READY magneto-cell 1`   | Booted (an Uno also reboots whenever the port is opened)       |
| `OK` / `ERR reason`      | Exactly one per command                                        |
| `CELL 13 h`              | The cell now shows mask 0x13 (bit 0 = dot 1) for letter `h`; `-` = blank, `_` = word gap |
| `END done` / `END stopped` | A `SPELL` finished, or was cut short by another command. Every `SPELL` gets exactly one. |

## Behavior worth knowing

- **Clear between letters.** There is always an all-down gap after each letter,
  so the two L's in "hello" read as two letters.
- **Dots are pushed up and held; gravity lowers them.** Servos stay powered
  while a letter is shown. The piston simply rests on the horn tip, so DOWN
  only has to lean the arm out of the way.
- **Gentle power-up.** Each servo's first pulse is its DOWN position, so
  nothing jumps to 90°. The servos also start 150 ms apart.
- **Staggered moves.** Within a letter, servos start 20 ms apart instead of all
  at once, which lowers the peak current draw. Use `TIMING ... 0` to move them
  together.
- **Safe settings.** EEPROM settings carry a checksum and are tied to the angle
  constants they were made from. Blank, corrupt or outdated settings fall back
  to the defaults.
- **No computer needed for a demo.** Set `BOOT_TEXT` in the sketch to
  `"hello"` and the board spells it at power-up.
- **Unexpected restarts.** If the board prints `READY` while running (the
  Jetson logs `Arduino restarted`), the servos are probably pulling the supply
  down. Check the separate servo supply and the shared ground.

## From the Jetson

`cane-vision` finds the board automatically (`cell.port: auto` in its
`config.yaml`) and sends its `braille:` timing on connect without saving it.
It falls back to the on-screen preview if no Arduino is connected.

```bash
cd cane-vision
.venv/bin/python -m cane_vision.serial_cell hello              # spell a word
.venv/bin/python -m cane_vision.serial_cell --send CONFIG      # any command
.venv/bin/python -m cane_vision --cell /dev/ttyACM0            # full pipeline
```

## Test without hardware

```bash
cd cell-firmware
make test                       # firmware logic tests
make sim && ./build/cell_sim -v # type commands; servo moves print on stderr
```

The `cane-vision` tests also build the simulator. They run the Python serial
driver against it through a pseudo-terminal, which checks the protocol and
confirms that the firmware's Braille table matches `braille.py`.
