$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (!(Test-Path .venv/Scripts/python.exe)) {
    throw 'Project Python environment is missing. Run scripts/setup.ps1 first.'
}
& .venv/Scripts/python.exe -c 'import cv2, fastapi, httpx, numpy, PIL, serial, uvicorn, yaml'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.AddressState -eq 'Preferred' -and $_.InterfaceAlias -match '^(Wi-Fi|Ethernet)' -and $_.IPAddress -notlike '169.254.*' }
foreach ($address in $addresses) { Write-Output "Local IPv4 ($($address.InterfaceAlias)): $($address.IPAddress)" }
& .venv/Scripts/python.exe -m serial.tools.list_ports
Write-Output 'Manual photo upload and lighting are available. Automatic strip lighting is unavailable.'
Write-Output 'The status indicator requires approved firmware and LEO_STATUS_PORT.'
& .venv/Scripts/python.exe -m ai_engine.main @args
exit $LASTEXITCODE
