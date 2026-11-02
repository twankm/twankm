@echo off
setlocal
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (
    echo Backend environment missing. Run backend\setup.ps1 first.
    pause
    exit /b 1
)
"backend\.venv\Scripts\python.exe" "scripts\dev.py" %*
if errorlevel 1 (
    echo.
    echo Startup failed. See the error above.
    pause
    exit /b 1
)
endlocal
