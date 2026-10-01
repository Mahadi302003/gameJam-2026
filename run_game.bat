@echo off
cd /d "%~dp0"
py -3.13 main.py
if %ERRORLEVEL% NEQ 0 (
    python main.py
)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Game exited with error code %ERRORLEVEL%.
    pause
)
