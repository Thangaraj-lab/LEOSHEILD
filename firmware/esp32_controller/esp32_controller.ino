#include <Arduino.h>

#include "communication.h"

void setup() {
  Serial.begin(115200);
}

void loop() {
  pollCommands(Serial);
  delay(1);
}
