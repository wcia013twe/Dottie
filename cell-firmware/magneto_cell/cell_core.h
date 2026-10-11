// Magneto one-cell firmware logic: Braille table, letter timing, serial
// commands and staggered servo moves.
//
// Plain C++ with no Arduino headers, so the same code runs on the Uno and in
// the host tests and simulator. The sketch supplies a Hardware object that
// moves servos, prints lines and saves settings.
//
// Dot numbering as read from above; bit 0 is dot 1, bit 5 is dot 6:
//
//     1  4
//     2  5
//     3  6

#pragma once

#include <stddef.h>
#include <stdint.h>

#define MAGNETO_CELL_VERSION "1"

namespace magneto {

const uint8_t DOT_COUNT = 6;
const uint8_t BLANK = 0x00;
const uint8_t ALL_UP = 0x3F;
const uint8_t MAX_TEXT = 64;    // letters and spaces kept from one SPELL
const uint8_t MAX_LINE = 96;    // longest accepted command line
const uint16_t PULSE_MIN_US = 500;
const uint16_t PULSE_MAX_US = 2500;
const uint16_t MAX_STEP_MS = 60000;
const uint16_t MAX_STAGGER_MS = 200;
// ---- Dot angles: edit these, re-flash, and they take effect --------------
// Angles are in degrees, measured from where the horn sits at 1500 us (as it
// was fitted). Positive turns one way, negative the other. Dots 1-3 use them
// as written; dots 4-6 are multiplied by RIGHT_BANK_DIR (-1 = mirror image).
// If a whole bank moves backwards, flip its *_BANK_DIR between 1 and -1.
const int16_t EXTENDED_ANGLE_DEG = 10;  // dot UP (pressed, red line)
const int16_t REST_ANGLE_DEG = -32;       // dot DOWN (rest, blue line)
const int8_t LEFT_BANK_DIR = 1;          // dots 1-3
const int8_t RIGHT_BANK_DIR = -1;        // dots 4-6
const uint16_t US_PER_10_DEG = 105;      // SG90: about 10.5 us per degree

// Pulse for `deg` degrees from the 1500 us position, clamped to the legal range.
uint16_t angleToPulse(int16_t deg, int8_t dir);

struct Settings {
  uint16_t up_us[DOT_COUNT];    // pulse that raises each dot
  uint16_t down_us[DOT_COUNT];  // pulse that lowers each dot
  uint16_t hold_ms;             // how long each letter is shown
  uint16_t gap_ms;              // all-down gap between letters
  uint16_t word_ms;             // all-down gap between words
  uint16_t stagger_ms;          // delay between starting each servo's move
};

Settings defaultSettings();
bool validSettings(const Settings& s);
uint16_t checksum(const Settings& s);

// Grade 1 mask for a-z (either case); 0 for anything else.
uint8_t letterMask(char c);

class Hardware {
 public:
  virtual void writeServo(uint8_t dot, uint16_t pulse_us) = 0;  // dot 0..5
  virtual void println(const char* line) = 0;
  virtual bool save(const Settings& s) = 0;

 protected:
  ~Hardware() {}
};

class Cell {
 public:
  explicit Cell(Hardware& hw, const Settings& s = defaultSettings());

  // Lower every dot and announce READY. Call once the servos are attached.
  void begin(uint32_t now);
  // Feed serial bytes; a full line runs as a command.
  void feed(char c, uint32_t now);
  void handleLine(char* line, uint32_t now);
  // Advance the letter timing and move servos. Call every loop.
  void update(uint32_t now);

  void spell(const char* text, uint32_t now);
  void setSettings(const Settings& s) {
    s_ = s;
    dirty_ = ALL_UP;
  }

  uint8_t mask() const { return target_; }
  bool spelling() const { return spelling_; }
  const Settings& settings() const { return s_; }

 private:
  void show(uint8_t mask, char shown);
  void stopSpelling();
  void moveServos(uint32_t now);
  void printConfig();
  void reply(bool ok, const char* error = 0);

  Hardware& hw_;
  Settings s_;

  // Spelling: text_ holds lowercase letters and single spaces.
  char text_[MAX_TEXT + 1];
  uint8_t len_ = 0;
  uint8_t pos_ = 0;         // letter being shown, or the next one during a gap
  bool inGap_ = false;
  bool spelling_ = false;
  uint32_t stepEnd_ = 0;

  // Servos: target_ is what the cell should show, applied_ what has been sent.
  uint8_t target_ = BLANK;
  uint8_t applied_ = BLANK;
  uint8_t dirty_ = 0;       // dots to rewrite even if unchanged (new calibration)
  uint8_t jogged_ = 0;      // dots under manual JOG, left alone until the next change
  uint32_t nextMove_ = 0;

  char line_[MAX_LINE + 1];
  uint8_t lineLen_ = 0;
  bool overflow_ = false;
};

}  // namespace magneto
