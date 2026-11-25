$ErrorActionPreference = 'Stop'
$pythonExe = 'python'
$dbPath = if ($env:DATABASE_PATH) { $env:DATABASE_PATH } else { 'storage/database/leo_shield.sqlite3' }
$prompted = $false
$ownerCount = 0
if (Test-Path -LiteralPath $dbPath) {
  $ownerCount = [int](& $pythonExe -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); t=c.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?',('table','users')).fetchone(); print(c.execute('SELECT count(*) FROM users').fetchone()[0] if t else 0)" $dbPath)
  if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the configured SQLite database.' }
}
if (-not $env:BOOTSTRAP_PASSWORD -and $ownerCount -eq 0) {
  $securePassword = Read-Host 'First-run LEO Shield owner password' -AsSecureString
  if ($securePassword.Length -lt 1) { throw 'A non-empty password is required for first-run owner setup.' }
  $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
  try { $env:BOOTSTRAP_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer) }
  $prompted = $true
}
try {
  & $pythonExe -c "from backend.app.main import initialize; initialize()"
  if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the local database.' }
  & $pythonExe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
} finally {
  if ($prompted) {
    Remove-Item Env:BOOTSTRAP_PASSWORD -ErrorAction SilentlyContinue
    $securePassword.Dispose()
    Remove-Variable securePassword -ErrorAction SilentlyContinue
  }
}
