// Host tests for the firmware logic: make test
#include <stdio.h>
#include <string.h>

#include <string>
#include <utility>
#include <vector>

#include "../magneto_cell/cell_core.h"

using magneto::Cell;
using magneto::Settings;
using magneto::defaultSettings;
using magneto::validSettings;
using magneto::angleToPulse;
using magneto::EXTENDED_ANGLE_DEG;
using magneto::REST_ANGLE_DEG;
using magneto::LEFT_BANK_DIR;
using magneto::RIGHT_BANK_DIR;
static const uint16_t PULSE_MAX_US_ = magneto::PULSE_MAX_US;
static const uint16_t PULSE_MIN_US_ = magneto::PULSE_MIN_US;

static int failures = 0;
#define CHECK(cond)                                                    \
  do {                                                                 \
    if (!(cond)) {                                                     \
      printf("  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);         \
      failures++;                                                      \
    }                                                                  \
  } while (0)

struct FakeHardware : magneto::Hardware {
  std::vector<std::string> lines;
  std::vector<std::pair<int, int>> writes;  // (dot, pulse)
  int pulse[magneto::DOT_COUNT] = {0, 0, 0, 0, 0, 0};
  int saves = 0;

  void writeServo(uint8_t dot, uint16_t us) override {
    writes.push_back(std::make_pair((int)dot, (int)us));
    pulse[dot] = us;
  }
  void println(const char* line) override { lines.push_back(line); }
  bool save(const Settings&) override {
    saves++;
    return true;
  }
};

static void send(Cell& cell, const char* text, uint32_t now) {
  for (const char* p = text; *p; p++) cell.feed(*p, now);
  cell.feed('\n', now);
}

static std::string last(const FakeHardware& hw) { return hw.lines.empty() ? "" : hw.lines.back(); }

// Runs the clock from `from` to `to` and records each line with its time.
static std::vector<std::pair<uint32_t, std::string>> run(Cell& cell, FakeHardware& hw, uint32_t from,
                                                         uint32_t to) {
  std::vector<std::pair<uint32_t, std::string>> out;
  for (uint32_t t = from; t != to + 1; t++) {
    size_t before = hw.lines.size();
    cell.update(t);
    for (size_t i = before; i < hw.lines.size(); i++) out.push_back(std::make_pair(t, hw.lines[i]));
  }
  return out;
}

static void test_letter_table() {
  // HELLO from the hardware handoff notes.
  CHECK(magneto::letterMask('h') == 0x13);
  CHECK(magneto::letterMask('e') == 0x11);
  CHECK(magneto::letterMask('l') == 0x07);
  CHECK(magneto::letterMask('o') == 0x15);
  CHECK(magneto::letterMask('H') == 0x13);
  CHECK(magneto::letterMask('w') == 0x3A);
  CHECK(magneto::letterMask('1') == 0);
  CHECK(magneto::letterMask(' ') == 0);
}

static void test_begin_lowers_every_dot() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  CHECK(hw.lines[0] == "READY magneto-cell " MAGNETO_CELL_VERSION);
  run(cell, hw, 0, 200);
  CHECK(hw.writes.size() == 6);
  for (int i = 0; i < 6; i++) CHECK(hw.pulse[i] == cell.settings().down_us[i]);
}

static void test_spell_timing() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  send(cell, "TIMING 100 10 50 0", 0);
  hw.lines.clear();
  send(cell, "SPELL hello", 0);
  CHECK(hw.lines.size() == 2 && hw.lines[0] == "OK" && hw.lines[1] == "CELL 13 h");
  std::vector<std::pair<uint32_t, std::string>> want = {
      {100, "CELL 00 -"}, {110, "CELL 11 e"}, {210, "CELL 00 -"}, {220, "CELL 07 l"},
      {320, "CELL 00 -"}, {330, "CELL 07 l"}, {430, "CELL 00 -"}, {440, "CELL 15 o"},
      {540, "CELL 00 -"}, {540, "END done"},
  };
  CHECK(run(cell, hw, 1, 1000) == want);
  CHECK(!cell.spelling());
  for (int i = 0; i < 6; i++) CHECK(hw.pulse[i] == cell.settings().down_us[i]);
}

static void test_word_gap() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  send(cell, "TIMING 100 10 50", 0);
  send(cell, "spell  A   b ", 0);
  CHECK(last(hw) == "CELL 01 a");
  std::vector<std::pair<uint32_t, std::string>> want = {
      {100, "CELL 00 _"}, {150, "CELL 03 b"}, {250, "CELL 00 -"}, {250, "END done"}};
  CHECK(run(cell, hw, 1, 500) == want);
}

static void test_spell_skips_non_letters() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  send(cell, "TIMING 10 1 5", 0);
  send(cell, "S   Trash-Can 42 ", 0);
  std::string shown;
  for (auto& l : hw.lines)
    if (l.rfind("CELL", 0) == 0 && l[8] != '-') shown += l[8];
  for (auto& e : run(cell, hw, 1, 500))
    if (e.second.rfind("CELL", 0) == 0 && e.second[8] != '-') shown += e.second[8];
  CHECK(shown == "trashcan");
}

static void test_new_word_interrupts() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  send(cell, "TIMING 100 10 50", 0);
  send(cell, "SPELL hello", 0);
  run(cell, hw, 1, 50);
  hw.lines.clear();
  send(cell, "SPELL ab", 50);
  CHECK(hw.lines.size() == 3);
  CHECK(hw.lines[0] == "END stopped" && hw.lines[1] == "OK" && hw.lines[2] == "CELL 01 a");
  int ends = 0;
  for (auto& e : run(cell, hw, 51, 2000)) ends += e.second.rfind("END", 0) == 0;
  CHECK(ends == 1);
}

static void test_empty_spell_still_ends() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  hw.lines.clear();
  send(cell, "SPELL 123 !", 0);
  CHECK(hw.lines.size() == 3 && hw.lines[1] == "CELL 00 -" && hw.lines[2] == "END done");
}

static void test_clear_stops_spelling() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  send(cell, "SPELL hello", 0);
  hw.lines.clear();
  send(cell, "CLEAR", 10);
  CHECK(hw.lines.size() == 3 && hw.lines[0] == "END stopped" && hw.lines[2] == "CELL 00 -");
  CHECK(!cell.spelling() && cell.mask() == 0);
}

static void test_dots_and_calibration() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  send(cell, "TIMING 3000 300 1000 0", 0);
  run(cell, hw, 0, 200);  // finish the staggered power-up moves
  send(cell, "CAL 1 1800 1200", 200);
  send(cell, "CAL 5 1100 1900", 200);  // mirrored horn: UP is the shorter pulse
  send(cell, "DOTS 125", 200);
  CHECK(last(hw) == "CELL 13 -");
  cell.update(201);
  const Settings d = defaultSettings();
  CHECK(hw.pulse[0] == 1800 && hw.pulse[1] == d.up_us[1] && hw.pulse[4] == 1100);
  CHECK(hw.pulse[2] == d.down_us[2] && hw.pulse[3] == d.down_us[3] && hw.pulse[5] == d.down_us[5]);
  send(cell, "DOTS 1, 2 5 6", 201);
  CHECK(cell.mask() == 0x33);
  send(cell, "DOTS", 202);
  cell.update(202);
  CHECK(hw.pulse[0] == 1200 && hw.pulse[4] == 1900);
  // New endpoints show immediately.
  send(cell, "CAL 1 1800 1250", 203);
  cell.update(203);
  CHECK(hw.pulse[0] == 1250);
}

// The angle constants become the default pulses; dots 4-6 are mirrored.
static void test_default_endpoints_come_from_angles() {
  const Settings d = defaultSettings();
  for (int i = 0; i < 3; i++)
    CHECK(d.up_us[i] == angleToPulse(EXTENDED_ANGLE_DEG, LEFT_BANK_DIR) &&
          d.down_us[i] == angleToPulse(REST_ANGLE_DEG, LEFT_BANK_DIR));
  for (int i = 3; i < 6; i++)
    CHECK(d.up_us[i] == angleToPulse(EXTENDED_ANGLE_DEG, RIGHT_BANK_DIR) &&
          d.down_us[i] == angleToPulse(REST_ANGLE_DEG, RIGHT_BANK_DIR));
  CHECK(angleToPulse(-15, 1) == 1343 && angleToPulse(32, 1) == 1836);
  CHECK(angleToPulse(-15, -1) == 1657 && angleToPulse(32, -1) == 1164);
  CHECK(angleToPulse(150, 1) == PULSE_MAX_US_ && angleToPulse(150, -1) == PULSE_MIN_US_);
  CHECK(validSettings(d));
}

static void test_moves_are_staggered() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  run(cell, hw, 0, 500);
  send(cell, "TIMING 3000 300 1000 20", 500);
  hw.writes.clear();
  send(cell, "DOTS 123456", 1000);
  std::vector<uint32_t> times;
  for (uint32_t t = 1000; t <= 1200; t++) {
    size_t before = hw.writes.size();
    cell.update(t);
    if (hw.writes.size() > before) times.push_back(t);
  }
  CHECK((times == std::vector<uint32_t>{1000, 1020, 1040, 1060, 1080, 1100}));
}

static void test_jog_holds_until_next_change() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  send(cell, "TIMING 3000 300 1000 0", 0);
  cell.update(0);
  send(cell, "JOG 2 1000", 1);
  CHECK(hw.pulse[1] == 1000 && last(hw) == "OK");
  run(cell, hw, 1, 100);
  CHECK(hw.pulse[1] == 1000);
  send(cell, "DOTS", 100);
  cell.update(100);
  CHECK(hw.pulse[1] == defaultSettings().down_us[1]);
}

static void test_errors() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  const char* bad[] = {"FOO", "CAL 7 1500 1500", "CAL 1 100 1500", "CAL 1 1500", "DOTS 7",
                       "DOTS 1x", "TIMING 1 2", "TIMING 1 2 3 999", "TIMING -1 2 3", "JOG 1 3000"};
  for (const char* line : bad) {
    send(cell, line, 0);
    CHECK(last(hw).rfind("ERR", 0) == 0);
  }
  CHECK(cell.settings().hold_ms == 3000);
  std::string long_line(200, 'x');
  send(cell, long_line.c_str(), 0);
  CHECK(last(hw) == "ERR line too long");
  send(cell, "PING", 0);
  CHECK(hw.lines[hw.lines.size() - 2] == "PONG magneto-cell " MAGNETO_CELL_VERSION && last(hw) == "OK");
}

static void test_crlf_and_blank_lines() {
  FakeHardware hw;
  Cell cell(hw);
  cell.begin(0);
  size_t before = hw.lines.size();
  const char* text = "\r\n\r\nping\r\n";
  for (const char* p = text; *p; p++) cell.feed(*p, 0);
  CHECK(hw.lines.size() == before + 2 && last(hw) == "OK");
}

static void test_config_round_trip_and_save() {
  FakeHardware a_hw, b_hw;
  Cell a(a_hw), b(b_hw);
  a.begin(0);
  b.begin(0);
  send(a, "CAL 3 2100 900", 0);
  send(a, "TIMING 2500 250 800 10", 0);
  a_hw.lines.clear();
  send(a, "CONFIG", 0);
  CHECK(a_hw.lines.size() == 8 && a_hw.lines[2] == "CAL 3 2100 900" && a_hw.lines[6] == "TIMING 2500 250 800 10");
  for (size_t i = 0; i + 1 < a_hw.lines.size(); i++) send(b, a_hw.lines[i].c_str(), 0);
  CHECK(magneto::checksum(a.settings()) == magneto::checksum(b.settings()));
  CHECK(magneto::checksum(a.settings()) != magneto::checksum(magneto::defaultSettings()));
  send(a, "SAVE", 0);
  CHECK(a_hw.saves == 1 && last(a_hw) == "OK");
  send(a, "DEFAULTS", 0);
  CHECK(magneto::checksum(a.settings()) == magneto::checksum(magneto::defaultSettings()));
}

static void test_settings_validation() {
  Settings s = magneto::defaultSettings();
  CHECK(magneto::validSettings(s));
  s.up_us[2] = 3000;
  CHECK(!magneto::validSettings(s));
  s = magneto::defaultSettings();
  s.stagger_ms = 0xFFFF;  // erased EEPROM
  CHECK(!magneto::validSettings(s));
}

static void test_millis_wraparound() {
  FakeHardware hw;
  Cell cell(hw);
  uint32_t start = 0xFFFFFFF0u;
  cell.begin(start);
  send(cell, "TIMING 100 10 50", start);
  send(cell, "SPELL ab", start);
  auto events = run(cell, hw, start + 1, start + 400);
  CHECK(events.size() == 4 && events[0].first == start + 100 && events.back().second == "END done");
}

int main() {
  test_letter_table();
  test_begin_lowers_every_dot();
  test_spell_timing();
  test_word_gap();
  test_spell_skips_non_letters();
  test_new_word_interrupts();
  test_empty_spell_still_ends();
  test_clear_stops_spelling();
  test_dots_and_calibration();
  test_default_endpoints_come_from_angles();
  test_moves_are_staggered();
  test_jog_holds_until_next_change();
  test_errors();
  test_crlf_and_blank_lines();
  test_config_round_trip_and_save();
  test_settings_validation();
  test_millis_wraparound();
  if (failures) {
    printf("%d check(s) failed\n", failures);
    return 1;
  }
  printf("All firmware logic tests passed.\n");
  return 0;
}
