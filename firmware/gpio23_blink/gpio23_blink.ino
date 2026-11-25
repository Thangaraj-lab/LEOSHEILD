#include <Arduino.h>

#if !defined(CONFIG_IDF_TARGET_ESP32)
#error "Select the original ESP32 target and verify the board's P23 pin before upload."
#endif

namespace {
constexpr uint8_t kLedPin = 23;
constexpr unsigned long kHalfPeriodMs = 500;
bool ledOn = false;
unsigned long lastChangeMs = 0;
}

void setup() {
  digitalWrite(kLedPin, LOW);
  pinMode(kLedPin, OUTPUT);
  Serial.begin(115200);
  Serial.println("LEO GPIO23 blink test");
  lastChangeMs = millis();
}

void loop() {
  const unsigned long now = millis();
  if (now - lastChangeMs >= kHalfPeriodMs) {
    lastChangeMs = now;
    ledOn = !ledOn;
    digitalWrite(kLedPin, ledOn ? HIGH : LOW);
    Serial.println(ledOn ? "GPIO23 HIGH" : "GPIO23 LOW");
  }
  delay(1);
}
