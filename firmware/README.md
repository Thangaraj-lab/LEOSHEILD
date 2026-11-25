# ESP32 USB diagnostics

The diagnostic sketch initializes serial at 115200 baud. It has no lighting GPIO assignments. Compile against a selected board target and obtain approval before flashing the identified device.

For the generic compile check, place the Arduino CLI Windows x64 executable in `.tools/arduino`, then run `./scripts/build_diagnostics.ps1 -InstallCore` once. Subsequent builds omit the flag to use the installed core. The generic build targets `esp32:esp32:esp32`. Board-specific compilation and USB verification follow physical identification. [Arduino CLI](https://docs.arduino.cc/arduino-cli/installation) · [Espressif Arduino core](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html)

Commands are uppercase ASCII and terminated by LF. CRLF is accepted. Each complete frame returns one line.

| Command | Response |
|---|---|
| `PING` | `OK PONG` |
| `VERSION` | `OK VERSION 0.1.0` |
| `STATUS` | `OK STATUS DIAGNOSTICS_ONLY LIGHT_OUTPUTS_DISABLED` |
| Other command | `ERR UNSUPPORTED_COMMAND` |
| Overlong or invalid frame | `ERR INVALID_FRAME` |

The parser bounds frames to 48 bytes and drops incomplete frames after 500 ms of inactivity. A compiled sketch alone does not verify USB behavior. Record the exact board and observed replies after approved flashing. Use [hardware preparation](../docs/hardware.md) before any lighting changes.
