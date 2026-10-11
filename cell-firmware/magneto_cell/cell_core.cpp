#include "cell_core.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace magneto {

namespace {

// Grade 1 letters a-z as dot masks (bit 0 = dot 1). Same table as
// cane-vision/cane_vision/braille.py.
const uint8_t LETTERS[26] = {
    0x01, 0x03, 0x09, 0x19, 0x11, 0x0B, 0x1B, 0x13, 0x0A, 0x1A,  // a-j
    0x05, 0x07, 0x0D, 0x1D, 0x15, 0x0F, 0x1F, 0x17, 0x0E, 0x1E,  // k-t
    0x25, 0x27, 0x3A, 0x2D, 0x3D, 0x35,                          // u-z
};

bool due(uint32_t now, uint32_t when) { return (int32_t)(now - when) >= 0; }

char* nextToken(char*& p) {
  while (*p && isspace((unsigned char)*p)) p++;
  if (!*p) return 0;
  char* start = p;
  while (*p && !isspace((unsigned char)*p)) p++;
  if (*p) *p++ = 0;
  return start;
}

bool nextNumber(char*& p, uint32_t lo, uint32_t hi, uint32_t& out) {
  char* token = nextToken(p);
  if (!token || !isdigit((unsigned char)*token)) return false;
  char* end;
  unsigned long value = strtoul(token, &end, 10);
  if (*end || value < lo || value > hi) return false;
  out = value;
  return true;
}

bool is(const char* token, const char* name) { return strcasecmp(token, name) == 0; }

}  // namespace

uint16_t angleToPulse(int16_t deg, int8_t dir) {
  int32_t us = 1500 + (int32_t)dir * deg * US_PER_10_DEG / 10;
  if (us < PULSE_MIN_US) us = PULSE_MIN_US;
  if (us > PULSE_MAX_US) us = PULSE_MAX_US;
  return (uint16_t)us;
}

Settings defaultSettings() {
  Settings s;
  // UP and DOWN come from the angle constants in cell_core.h.
  for (uint8_t i = 0; i < DOT_COUNT; i++) {
    int8_t dir = i < 3 ? LEFT_BANK_DIR : RIGHT_BANK_DIR;
    s.up_us[i] = angleToPulse(EXTENDED_ANGLE_DEG, dir);
    s.down_us[i] = angleToPulse(REST_ANGLE_DEG, dir);
  }
  s.hold_ms = 3000;
  s.gap_ms = 300;
  s.word_ms = 1000;
  s.stagger_ms = 20;
  return s;
}

bool validSettings(const Settings& s) {
  for (uint8_t i = 0; i < DOT_COUNT; i++) {
    if (s.up_us[i] < PULSE_MIN_US || s.up_us[i] > PULSE_MAX_US) return false;
    if (s.down_us[i] < PULSE_MIN_US || s.down_us[i] > PULSE_MAX_US) return false;
  }
  return s.hold_ms <= MAX_STEP_MS && s.gap_ms <= MAX_STEP_MS && s.word_ms <= MAX_STEP_MS &&
         s.stagger_ms <= MAX_STAGGER_MS;
}

uint16_t checksum(const Settings& s) {
  const uint8_t* bytes = reinterpret_cast<const uint8_t*>(&s);
  uint16_t h = 0xA5A5;
  for (size_t i = 0; i < sizeof(Settings); i++) h = (uint16_t)((h << 5) | (h >> 11)) ^ bytes[i];
  return h;
}

uint8_t letterMask(char c) {
  c = (char)tolower((unsigned char)c);
  return (c >= 'a' && c <= 'z') ? LETTERS[c - 'a'] : 0;
}

Cell::Cell(Hardware& hw, const Settings& s) : hw_(hw), s_(s) { text_[0] = 0; }

void Cell::begin(uint32_t now) {
  target_ = applied_ = BLANK;
  dirty_ = ALL_UP;
  jogged_ = 0;
  nextMove_ = now;
  hw_.println("READY magneto-cell " MAGNETO_CELL_VERSION);
  moveServos(now);
}

void Cell::feed(char c, uint32_t now) {
  if (c == '\n' || c == '\r') {
    if (overflow_) {
      reply(false, "line too long");
    } else if (lineLen_) {
      line_[lineLen_] = 0;
      handleLine(line_, now);
    }
    lineLen_ = 0;
    overflow_ = false;
  } else if (lineLen_ < MAX_LINE) {
    line_[lineLen_++] = c;
  } else {
    overflow_ = true;
  }
}

void Cell::handleLine(char* line, uint32_t now) {
  char* p = line;
  char* cmd = nextToken(p);
  if (!cmd) return;
  uint32_t a, b, c, d;

  if (is(cmd, "PING")) {
    hw_.println("PONG magneto-cell " MAGNETO_CELL_VERSION);
    reply(true);
  } else if (is(cmd, "SPELL") || is(cmd, "S")) {
    stopSpelling();
    reply(true);
    spell(p, now);
  } else if (is(cmd, "DOTS")) {
    uint8_t mask = 0;
    for (; *p; p++) {
      if (*p >= '1' && *p <= '6') mask |= 1 << (*p - '1');
      else if (*p != '0' && *p != ',' && !isspace((unsigned char)*p)) return reply(false, "dots are 1-6");
    }
    stopSpelling();
    reply(true);
    show(mask, '-');
  } else if (is(cmd, "CLEAR") || is(cmd, "C")) {
    stopSpelling();
    reply(true);
    show(BLANK, '-');
  } else if (is(cmd, "TIMING")) {
    d = s_.stagger_ms;
    bool ok = nextNumber(p, 0, MAX_STEP_MS, a) && nextNumber(p, 0, MAX_STEP_MS, b) &&
              nextNumber(p, 0, MAX_STEP_MS, c);
    while (*p && isspace((unsigned char)*p)) p++;
    if (!ok || (*p && !nextNumber(p, 0, MAX_STAGGER_MS, d)))
      return reply(false, "usage: TIMING hold_ms gap_ms word_ms [stagger_ms]");
    s_.hold_ms = a;
    s_.gap_ms = b;
    s_.word_ms = c;
    s_.stagger_ms = d;
    reply(true);
  } else if (is(cmd, "CAL")) {
    if (!nextNumber(p, 1, DOT_COUNT, a) || !nextNumber(p, PULSE_MIN_US, PULSE_MAX_US, b) ||
        !nextNumber(p, PULSE_MIN_US, PULSE_MAX_US, c))
      return reply(false, "usage: CAL dot up_us down_us (500-2500)");
    s_.up_us[a - 1] = b;
    s_.down_us[a - 1] = c;
    dirty_ |= 1 << (a - 1);  // show the new endpoint straight away
    reply(true);
  } else if (is(cmd, "JOG")) {
    if (!nextNumber(p, 1, DOT_COUNT, a) || !nextNumber(p, PULSE_MIN_US, PULSE_MAX_US, b))
      return reply(false, "usage: JOG dot pulse_us (500-2500)");
    stopSpelling();
    jogged_ |= 1 << (a - 1);
    hw_.writeServo(a - 1, b);
    reply(true);
  } else if (is(cmd, "CONFIG")) {
    printConfig();
    reply(true);
  } else if (is(cmd, "SAVE")) {
    reply(hw_.save(s_), "save failed");
  } else if (is(cmd, "DEFAULTS")) {
    s_ = defaultSettings();
    dirty_ = ALL_UP;
    reply(true);
  } else if (is(cmd, "HELP")) {
    hw_.println("COMMANDS PING SPELL DOTS CLEAR TIMING CAL JOG CONFIG SAVE DEFAULTS");
    reply(true);
  } else {
    reply(false, "unknown command, try HELP");
  }
}

void Cell::spell(const char* text, uint32_t now) {
  stopSpelling();
  // Keep letters, collapse whitespace to single spaces; skip anything else,
  // the same way braille.spell() does on the Jetson.
  len_ = 0;
  bool space = false;
  for (; *text && len_ < MAX_TEXT; text++) {
    if (letterMask(*text)) {
      if (space && len_) {
        if (len_ + 1 >= MAX_TEXT) break;
        text_[len_++] = ' ';
      }
      space = false;
      text_[len_++] = (char)tolower((unsigned char)*text);
    } else if (isspace((unsigned char)*text)) {
      space = true;
    }
  }
  text_[len_] = 0;

  if (!len_) {
    show(BLANK, '-');
    hw_.println("END done");
    return;
  }
  spelling_ = true;
  pos_ = 0;
  inGap_ = false;
  stepEnd_ = now + s_.hold_ms;
  show(letterMask(text_[0]), text_[0]);
}

void Cell::update(uint32_t now) {
  while (spelling_ && due(now, stepEnd_)) {
    if (inGap_) {
      inGap_ = false;
      stepEnd_ += s_.hold_ms;
      show(letterMask(text_[pos_]), text_[pos_]);
    } else if (pos_ + 1 >= len_) {
      spelling_ = false;
      show(BLANK, '-');
      hw_.println("END done");
    } else {
      // Always clear between letters, so the two L's in "hello" read as two.
      inGap_ = true;
      if (text_[pos_ + 1] == ' ') {
        stepEnd_ += s_.word_ms;
        pos_ += 2;
        show(BLANK, '_');
      } else {
        stepEnd_ += s_.gap_ms;
        pos_ += 1;
        show(BLANK, '-');
      }
    }
  }
  moveServos(now);
}

void Cell::show(uint8_t mask, char shown) {
  target_ = mask & ALL_UP;
  dirty_ |= jogged_;  // jogged dots return to their calibrated positions
  jogged_ = 0;
  char buf[16];
  snprintf(buf, sizeof buf, "CELL %02X %c", target_, shown);
  hw_.println(buf);
}

void Cell::stopSpelling() {
  if (!spelling_) return;
  spelling_ = false;
  hw_.println("END stopped");
}

// Start one servo at a time, `stagger_ms` apart, so six SG90s don't all draw
// their stall current at the same instant.
void Cell::moveServos(uint32_t now) {
  uint8_t pending = ((target_ ^ applied_) | dirty_) & ~jogged_ & ALL_UP;
  if (!pending) {
    if (due(now, nextMove_)) nextMove_ = now;  // keep the clock fresh while idle
    return;
  }
  for (uint8_t dot = 0; dot < DOT_COUNT && pending && due(now, nextMove_); dot++) {
    uint8_t bit = 1 << dot;
    if (!(pending & bit)) continue;
    bool up = target_ & bit;
    hw_.writeServo(dot, up ? s_.up_us[dot] : s_.down_us[dot]);
    applied_ = (applied_ & ~bit) | (target_ & bit);
    dirty_ &= ~bit;
    pending &= ~bit;
    nextMove_ = now + s_.stagger_ms;
  }
}

void Cell::printConfig() {
  char buf[40];
  for (uint8_t i = 0; i < DOT_COUNT; i++) {
    snprintf(buf, sizeof buf, "CAL %u %u %u", (unsigned)(i + 1), (unsigned)s_.up_us[i],
             (unsigned)s_.down_us[i]);
    hw_.println(buf);
  }
  snprintf(buf, sizeof buf, "TIMING %u %u %u %u", (unsigned)s_.hold_ms, (unsigned)s_.gap_ms,
           (unsigned)s_.word_ms, (unsigned)s_.stagger_ms);
  hw_.println(buf);
}

void Cell::reply(bool ok, const char* error) {
  if (ok) {
    hw_.println("OK");
    return;
  }
  char buf[64];
  snprintf(buf, sizeof buf, "ERR %s", error);
  hw_.println(buf);
}

}  // namespace magneto
