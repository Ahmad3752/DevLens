$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Virtual environment not found at $Python. Create it first with: python -m venv .venv"
}

Push-Location (Join-Path $Root "backend")
try {
    & $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
}
finally {
    Pop-Location
}
