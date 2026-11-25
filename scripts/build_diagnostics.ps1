param([switch]$InstallCore)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$arduinoRoot = (Resolve-Path .tools/arduino).Path
$arduinoCli = Join-Path $arduinoRoot 'arduino-cli.exe'
$env:ARDUINO_DIRECTORIES_DATA = Join-Path $arduinoRoot 'data'
$env:ARDUINO_DIRECTORIES_DOWNLOADS = Join-Path $arduinoRoot 'downloads'
$env:ARDUINO_DIRECTORIES_USER = Join-Path $arduinoRoot 'user'
$env:ARDUINO_UPDATER_ENABLE_NOTIFICATION = 'false'

if ($InstallCore) {
    & $arduinoCli core install esp32:esp32@3.3.12 --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& $arduinoCli compile --fqbn esp32:esp32:esp32 --build-path .tools/arduino/diagnostics-build firmware/esp32_controller
exit $LASTEXITCODE
