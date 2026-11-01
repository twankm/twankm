param(
    [string]$Python = ''
)

$ErrorActionPreference = 'Stop'
if (!$Python) {
    $localRuntime = Join-Path $PSScriptRoot '.python-runtime\python.exe'
    if (Test-Path -LiteralPath $localRuntime) {
        $Python = $localRuntime
    } else {
        $Python = (Get-Command python -ErrorAction Stop).Source
    }
}

# Validate the base interpreter before touching the current environment.
& $Python -c 'import sys; print(sys.version); sys.exit(0 if (3, 10) <= sys.version_info[:2] < (3, 15) else 1)'
if ($LASTEXITCODE -ne 0) {
    throw 'Use a working Python 3.10-3.14 interpreter; Python 3.13 is recommended. Pass its path with -Python.'
}
$basePython = & $Python -c 'import sys; print(sys._base_executable)'
if ($LASTEXITCODE -ne 0) { throw 'Could not locate the base Python interpreter.' }
$basePython = $basePython.Trim()
$environmentPath = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '.venv'))
$backendRoot = [IO.Path]::GetFullPath($PSScriptRoot)
if ((Split-Path $environmentPath -Parent) -ne $backendRoot) {
    throw 'Environment path must remain inside backend.'
}
if (Test-Path -LiteralPath $environmentPath) {
    $backupPath = Join-Path $backendRoot ('.venv.before-' + [guid]::NewGuid().ToString('N'))
    if ((Split-Path $backupPath -Parent) -ne $backendRoot) { throw 'Invalid backup path.' }
    Move-Item -LiteralPath $environmentPath -Destination $backupPath
    Write-Host "Previous environment preserved at $backupPath"
}
& $basePython -m venv $environmentPath
if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv.' }
$backendPython = Join-Path $environmentPath 'Scripts\python.exe'
& $backendPython -m pip install -e "${PSScriptRoot}[dev]"
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Re-run setup.ps1 after resolving the reported error.' }
Write-Host 'Backend ready. Run backend/start.ps1; activation is optional.'
