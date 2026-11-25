$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
& .venv/Scripts/python.exe -m ai_engine.main @args
exit $LASTEXITCODE
