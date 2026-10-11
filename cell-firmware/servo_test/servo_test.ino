// Magneto servo test: checks that all six dot servos move, before running
// the real firmware (../magneto_cell). Same pins: D2-D7 = dots 1-6.
//
// Open the Serial Monitor at 115200 baud. The test runs on its own, over and
// over:
//   1. each servo in turn swings LOW -> HIGH -> LOW, then returns to CENTER
//   2. all six swing together, twice (the hardest moment for the supply)
//
// Send a key to take over (any line ending works):
//   1-6  wiggle just that servo        a  all to HIGH     z  all to LOW
//   c    all to CENTER                 r  resume the automatic test
//
// If "servo test starting" reappears by itself, the board reset: the servos
// are pulling the supply down. Check the servo supply and the shared ground.

#include <Servo.h>

const uint8_t DOT_COUNT = 6;
const uint8_t SERVO_PINS[DOT_COUNT] = {2, 3, 4, 5, 6, 7};  // dots 1-6

// Pulse widths in microseconds. 1500 is the middle of an SG90's range and
// roughly 10 us is one degree, so 1300-1700 is about 40 degrees of swing.
// This only checks wiring and power. The real UP/DOWN positions live in
// magneto_cell.
const uint16_t CENTER_US = 1500;
const uint16_t LOW_US = 1300;
const uint16_t HIGH_US = 1700;

const uint16_t MOVE_MS = 600;   // time allowed for each move
const uint16_t ATTACH_STAGGER_MS = 150;

Servo servos[DOT_COUNT];
bool automatic = true;
char pendingKey = 0;

// Wait, but stop early if a key arrives. Returns false if interrupted.
bool pause(uint16_t ms) {
  uint32_t start = millis();
  while (millis() - start < ms) {
    while (Serial.available()) {
      char c = Serial.read();
      if (c != '\n' && c != '\r' && c != ' ') pendingKey = c;
    }
    if (pendingKey) return false;
  }
  return true;
}

void moveOne(uint8_t i, uint16_t us, const char* name) {
  servos[i].writeMicroseconds(us);
  Serial.print(F("dot "));
  Serial.print(i + 1);
  Serial.print(F(" (D"));
  Serial.print(SERVO_PINS[i]);
  Serial.print(F(") -> "));
  Serial.print(name);
  Serial.print(' ');
  Serial.print(us);
  Serial.println(F(" us"));
}

void moveAll(uint16_t us, const char* name) {
  for (uint8_t i = 0; i < DOT_COUNT; i++) servos[i].writeMicroseconds(us);
  Serial.print(F("all -> "));
  Serial.print(name);
  Serial.print(' ');
  Serial.print(us);
  Serial.println(F(" us"));
}

bool wiggle(uint8_t i) {
  moveOne(i, LOW_US, "LOW");
  if (!pause(MOVE_MS)) return false;
  moveOne(i, HIGH_US, "HIGH");
  if (!pause(MOVE_MS)) return false;
  moveOne(i, LOW_US, "LOW");
  if (!pause(MOVE_MS)) return false;
  moveOne(i, CENTER_US, "CENTER");
  return pause(MOVE_MS);
}

void runAutomaticTest() {
  Serial.println(F("-- one at a time --"));
  for (uint8_t i = 0; i < DOT_COUNT; i++)
    if (!wiggle(i)) return;

  Serial.println(F("-- all together --"));
  for (uint8_t n = 0; n < 2; n++) {
    moveAll(LOW_US, "LOW");
    if (!pause(MOVE_MS)) return;
    moveAll(HIGH_US, "HIGH");
    if (!pause(MOVE_MS)) return;
  }
  moveAll(CENTER_US, "CENTER");
  pause(1500);
}

void handleKey(char key) {
  if (key >= '1' && key <= '6') {
    automatic = false;
    wiggle(key - '1');
  } else if (key == 'a' || key == 'A') {
    automatic = false;
    moveAll(HIGH_US, "HIGH");
  } else if (key == 'z' || key == 'Z') {
    automatic = false;
    moveAll(LOW_US, "LOW");
  } else if (key == 'c' || key == 'C') {
    automatic = false;
    moveAll(CENTER_US, "CENTER");
  } else if (key == 'r' || key == 'R') {
    automatic = true;
    Serial.println(F("automatic test resumed"));
  } else {
    Serial.println(F("keys: 1-6 wiggle one, a HIGH, z LOW, c CENTER, r resume"));
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println(F("servo test starting"));

  // Start each servo at CENTER and power them up one at a time, so six
  // servos don't jump at once.
  for (uint8_t i = 0; i < DOT_COUNT; i++) {
    servos[i].writeMicroseconds(CENTER_US);
    servos[i].attach(SERVO_PINS[i], 500, 2500);
    servos[i].writeMicroseconds(CENTER_US);
    moveOne(i, CENTER_US, "CENTER");
    delay(ATTACH_STAGGER_MS);
  }
  Serial.println(F("keys: 1-6 wiggle one, a HIGH, z LOW, c CENTER, r resume"));
}

void loop() {
  if (automatic) runAutomaticTest();
  else pause(50);

  // A key interrupted the test (or arrived while idle): act on it. Keys sent
  // during a wiggle cut it short and are handled next.
  while (pendingKey) {
    char key = pendingKey;
    pendingKey = 0;
    handleKey(key);
  }
}
