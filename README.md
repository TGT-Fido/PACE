# PACE26 - Version 7.0.0

PACE (Projects At a glanCE) is a local project dashboard with Cards, Canvas, Radial Map and Roadmap, PDF viewing, search and editable project metadata.

## Install on Windows

Run `PACE-7.0.0-Setup.exe`. This is a complete per-user Windows x64 installation with a private Python 3.13.7 runtime. You do not need an older PACE installation or a separate Python installation. It does not modify your system Python or PATH. The installer is unsigned; Windows may request confirmation.

Launch PACE from the Start menu or desktop. The tray menu offers Open dashboard, Open PACE folder, Settings and Exit. The host computer must stay on and PACE must stay running for other devices to connect.

Start in **This computer only** mode at `http://127.0.0.1:8765`. Tray Settings can switch to **Local network** or **Tailscale** and show usable addresses. Tailscale is optional and must already be installed, connected and signed in for that mode.

HDR is optional and restricted to a localhost address on the host PC. Standard rendering works on all three connection modes. See `docs/USER_GUIDE.md` and the verification limits in `docs/V7_VALIDATION.md`.

## Existing users

Keep a full backup of the old installation, especially `data`. Exit the older PACE tray before starting V7; two copies cannot use the same address and port. For a safe migration, install V7 into a separate folder, uncheck Open PACE at the end, and copy your old `data` folder into the new installation before the first launch. Never overwrite an existing V7 data folder without first backing it up. The new app uses the migrated data; samples are installed only into a completely fresh data folder. Uninstall keeps `data` and backups.

The source/portable ZIP contains the same runtime and app. Extract it to a writable folder and run `START_PACE.cmd`. Do not run from inside the ZIP. Linux/macOS developers can use Python 3.10+ with `python app/server.py --open`; the Windows tray and bundled runtime are Windows-only.

V7.1 GitHub update deployment is a subsequent test, after the repository and release assets are configured. This package does not claim a completed end-to-end GitHub update test.
