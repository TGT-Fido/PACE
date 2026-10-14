"""Compatibility launcher; uses the tray on Windows and the server elsewhere."""
import subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
raise SystemExit(subprocess.call([sys.executable,str(root/('tray.pyw' if sys.platform=='win32' else 'server.py'))]+([] if sys.platform=='win32' else ['--open'])))
