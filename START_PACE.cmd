@echo off
cd /d "%~dp0"
if not exist "runtime\pythonw.exe" (
 echo The private Python runtime is missing. Run PACE-7.0.0-Setup.exe to repair this installation.
 pause
 exit /b 1
)
start "PACE" "runtime\pythonw.exe" "app\tray.pyw"
