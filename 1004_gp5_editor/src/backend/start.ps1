param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$backendPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $backendPython)) {
    throw 'Backend environment missing. Run backend/setup.ps1 first.'
}

# Resolve the application relative to this script, independent of the caller's cwd.
Push-Location $PSScriptRoot
try {
    & $backendPython -m uvicorn app.main:app --reload --reload-dir (Join-Path $PSScriptRoot 'app') --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw 'Backend startup failed. If the project was moved, run backend/setup.ps1 to rebuild .venv.'
    }
} finally {
    Pop-Location
}
