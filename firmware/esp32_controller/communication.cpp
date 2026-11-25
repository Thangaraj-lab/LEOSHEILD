#include "communication.h"

#include <cstring>

namespace {
constexpr char kFirmwareVersion[] = "0.1.0";
constexpr size_t kMaximumCommand = 48;
constexpr size_t kBytesPerPoll = 64;
constexpr uint32_t kPartialTimeoutMs = 500;

void reply(Stream& stream, const char* command) {
  if (std::strcmp(command, "PING") == 0) {
    stream.println("OK PONG");
  } else if (std::strcmp(command, "VERSION") == 0) {
    stream.print("OK VERSION ");
    stream.println(kFirmwareVersion);
  } else if (std::strcmp(command, "STATUS") == 0) {
    stream.println("OK STATUS DIAGNOSTICS_ONLY LIGHT_OUTPUTS_DISABLED");
  } else {
    stream.println("ERR UNSUPPORTED_COMMAND");
  }
}
}

void pollCommands(Stream& stream) {
  static char command[kMaximumCommand + 1];
  static size_t length = 0;
  static bool discarding = false;
  static uint32_t lastInput = 0;

  if ((length != 0 || discarding) && millis() - lastInput >= kPartialTimeoutMs) {
    length = 0;
    discarding = false;
  }

  for (size_t index = 0; index < kBytesPerPoll && stream.available() > 0; ++index) {
    const int byte = stream.read();
    if (byte < 0) {
      break;
    }
    lastInput = millis();
    if (byte == '\n') {
      if (discarding) {
        stream.println("ERR INVALID_FRAME");
      } else {
        if (length > 0 && command[length - 1] == '\r') {
          --length;
        }
        command[length] = '\0';
        reply(stream, command);
      }
      length = 0;
      discarding = false;
    } else if (!discarding) {
      if (length >= kMaximumCommand || (byte != '\r' && (byte < 0x20 || byte > 0x7e))) {
        discarding = true;
      } else {
        command[length++] = static_cast<char>(byte);
      }
    }
  }
}
