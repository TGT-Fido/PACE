@echo off
cd /d "%~dp0"
echo Exit PACE from the tray before using this diagnostic launcher.
"runtime\python.exe" "app\server.py" --host 127.0.0.1 --open
pause
