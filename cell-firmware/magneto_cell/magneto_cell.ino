// Magneto one-cell Braille display: Arduino Uno driving six SG90 servos.
//
// The Jetson (or the Serial Monitor) sends a word, e.g. "SPELL chair"; this
// board looks up each letter's dots, raises and lowers the servos, and holds
// each letter for the configured time. See ../README.md for wiring, the
// command list and calibration.
//
// The logic lives in cell_core.cpp so it can be tested on a computer; this
// file only connects it to the servos, the serial port and the EEPROM.

#include <EEPROM.h>
#include <Servo.h>

#include "cell_core.h"

const uint8_t SERVO_PINS[magneto::DOT_COUNT] = {2, 3, 4, 5, 6, 7};  // dots 1-6
const long BAUD = 115200;
const uint16_t ATTACH_STAGGER_MS = 150;  // power the servos up one at a time

// Spelled at power-up, so the cell can be demonstrated without a computer.
// Leave empty to start with all dots down.
const char BOOT_TEXT[] = "";

const uint32_t EEPROM_MAGIC = 0x324E474DUL;  // "MGN2"

// Saved settings are tied to the defaults they were made from: change the
// angle constants in cell_core.h, re-flash, and the new defaults take over.
struct Stored {
  uint32_t magic;
  uint16_t defaults_id;
  magneto::Settings settings;
  uint16_t checksum;
};

uint16_t defaultsId() { return magneto::checksum(magneto::defaultSettings()); }

class ArduinoHardware : public magneto::Hardware {
 public:
  Servo servos[magneto::DOT_COUNT];

  void writeServo(uint8_t dot, uint16_t pulse_us) override {
    servos[dot].writeMicroseconds(pulse_us);
  }

  void println(const char* line) override { Serial.println(line); }

  bool save(const magneto::Settings& s) override {
    Stored stored = {EEPROM_MAGIC, defaultsId(), s, magneto::checksum(s)};
    EEPROM.put(0, stored);  // only rewrites bytes that changed
    return true;
  }
};

magneto::Settings loadSettings() {
  Stored stored;
  EEPROM.get(0, stored);
  if (stored.magic == EEPROM_MAGIC && stored.defaults_id == defaultsId() &&
      stored.checksum == magneto::checksum(stored.settings) &&
      magneto::validSettings(stored.settings))
    return stored.settings;
  return magneto::defaultSettings();
}

ArduinoHardware hw;
magneto::Cell cell(hw);

void setup() {
  Serial.begin(BAUD);
  cell.setSettings(loadSettings());

  // Set each servo's first pulse to its DOWN position before attaching, so it
  // doesn't jump to the library's 90 degree default and push a dot up.
  for (uint8_t i = 0; i < magneto::DOT_COUNT; i++) {
    uint16_t down = cell.settings().down_us[i];
    hw.servos[i].writeMicroseconds(down);
    hw.servos[i].attach(SERVO_PINS[i], magneto::PULSE_MIN_US, magneto::PULSE_MAX_US);
    hw.servos[i].writeMicroseconds(down);
    delay(ATTACH_STAGGER_MS);
  }

  cell.begin(millis());
  if (BOOT_TEXT[0]) cell.spell(BOOT_TEXT, millis());
}

void loop() {
  while (Serial.available()) cell.feed((char)Serial.read(), millis());
  cell.update(millis());
}
