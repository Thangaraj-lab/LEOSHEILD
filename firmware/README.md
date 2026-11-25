# ESP32 USB diagnostics

The approval-gated inspection firmware is in `esp32_status_indicator/`. It runs on the original ESP32 target and uses GPIO23 only. It boots OFF and returns OFF after five seconds without a valid host request. At 115200 baud, send `LEO <hex-request-id> PING`, `GET_STATUS`, `SET_STATUS <state>` or `ALL_OFF` followed by LF. Responses use `LEO <id> <command> <firmware-version> <state> <OK-or-error>`. Possible states are `IDLE`, `CAPTURING`, `ANALYZING`, `AWAITING_CAPTURE`, `COMPLETED` and `ERROR`. Continuous ON indicates processing ended, including a job that ended on HOLD. It is not a quality decision.

Set `LEO_STATUS_PORT=COM5` or `auto` only after verifying the intended device and deploying the approved firmware. Automatic mode selects a CP210x bridge only when exactly one is available. Live availability requires a versioned acknowledgment. Inspection proceeds if the serial device disconnects.

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
