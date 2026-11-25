$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
& .venv/Scripts/python.exe -m pytest --basetemp .venv/pytest-work @args
exit $LASTEXITCODE
