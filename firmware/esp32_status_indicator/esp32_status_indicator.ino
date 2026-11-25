#include <Arduino.h>
#include <cstring>

#if !defined(CONFIG_IDF_TARGET_ESP32)
#error "Select the original ESP32 target."
#endif

namespace {
constexpr uint8_t kLedPin = 23;
constexpr uint32_t kTimeoutMs = 5000;
constexpr uint32_t kFrameTimeoutMs = 500;
constexpr char kVersion[] = "1.0.0";
enum State { Idle, Capturing, Analyzing, AwaitingCapture, Completed, Error };
const char* const kStates[] = {"IDLE", "CAPTURING", "ANALYZING", "AWAITING_CAPTURE", "COMPLETED", "ERROR"};
State state = Idle;
uint32_t stateSince = 0;
uint32_t lastContact = 0;

void setState(State next) {
  if (state != next) {
    state = next;
    stateSince = millis();
  }
}

bool ledOn(uint32_t elapsed) {
  switch (state) {
    case Capturing: return elapsed % 1200 < 600;
    case Analyzing: return elapsed % 300 < 150;
    case AwaitingCapture: return elapsed % 1600 < 480 && elapsed % 240 < 120;
    case Completed: return true;
    case Error: return elapsed % 1800 < 720 && elapsed % 240 < 120;
    default: return false;
  }
}

void acknowledge(const char* id, const char* command, const char* outcome) {
  Serial.printf("LEO %s %s %s %s %s\n", id, command, kVersion, kStates[state], outcome);
}

bool validId(const char* id) {
  return id && strlen(id) <= 16 && strspn(id, "0123456789abcdef") == strlen(id);
}

void command(char* frame) {
  char* cursor = nullptr;
  const char* prefix = strtok_r(frame, " ", &cursor);
  const char* id = strtok_r(nullptr, " ", &cursor);
  const char* name = strtok_r(nullptr, " ", &cursor);
  const char* value = strtok_r(nullptr, " ", &cursor);
  const char* extra = strtok_r(nullptr, " ", &cursor);
  if (!prefix || strcmp(prefix, "LEO") || !validId(id) || !name)
    return acknowledge("-", "-", "INVALID_FRAME");
  if (!strcmp(name, "SET_STATUS") && value && !extra) {
    for (unsigned i = 0; i < sizeof(kStates) / sizeof(kStates[0]); ++i) {
      if (!strcmp(value, kStates[i])) {
        setState(static_cast<State>(i));
        lastContact = millis();
        return acknowledge(id, name, "OK");
      }
    }
    return acknowledge(id, name, "INVALID_STATUS");
  }
  if (!value && (!strcmp(name, "PING") || !strcmp(name, "GET_STATUS") || !strcmp(name, "ALL_OFF"))) {
    if (!strcmp(name, "ALL_OFF")) setState(Idle);
    lastContact = millis();
    return acknowledge(id, name, "OK");
  }
  acknowledge(id, name, "INVALID_COMMAND");
}

void pollSerial() {
  static char frame[72];
  static size_t length = 0;
  static bool discard = false;
  static uint32_t lastByte = 0;
  if ((length || discard) && millis() - lastByte >= kFrameTimeoutMs) {
    length = 0;
    discard = false;
  }
  for (unsigned i = 0; i < 64 && Serial.available(); ++i) {
    const int byte = Serial.read();
    if (byte < 0) break;
    lastByte = millis();
    if (byte == '\n') {
      if (discard) acknowledge("-", "-", "INVALID_FRAME");
      else {
        frame[length] = '\0';
        command(frame);
      }
      length = 0;
      discard = false;
    } else if (byte != '\r' && !discard) {
      if (byte < 0x20 || byte > 0x7e || length == sizeof(frame) - 1) discard = true;
      else frame[length++] = static_cast<char>(byte);
    }
  }
}
}

void setup() {
  digitalWrite(kLedPin, LOW);
  pinMode(kLedPin, OUTPUT);
  Serial.begin(115200);
}

void loop() {
  pollSerial();
  if (millis() - lastContact >= kTimeoutMs) setState(Idle);
  digitalWrite(kLedPin, ledOn(millis() - stateSince) ? HIGH : LOW);
  delay(1);
}
