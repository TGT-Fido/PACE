# Rebuilding the Windows installer

Install NSIS 3.x on a build computer and run `makensis build/installer.nsi` from the package folder. The bundled app, defaults and private runtime are inputs. Output is PACE-7.0.0-Setup.exe at the package root. Override OUTPUT_FILE with an absolute path if needed. End users need neither NSIS nor a separate Python installation.

Tests: `python -m unittest discover -s docs/tests -p "test_*.py"`. Browser tests require Playwright, Chromium and a disposable data directory; see docs/tests/browser_v7.cjs. Do not point destructive browser tests at personal data.
