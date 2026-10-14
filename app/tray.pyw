"""PACE Windows tray launcher. Python standard library; no installer or packages.

Owns an in-process HTTP server. Exit stops only that server, never Tailscale.
The original CMD launcher remains available for troubleshooting.
"""
import ctypes as C
from ctypes import wintypes as W
import json
import logging
from pathlib import Path
import sys
import threading
import webbrowser

if sys.platform != 'win32':
    raise SystemExit('This launcher requires Windows.')

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / 'data'
U = C.WinDLL('user32', use_last_error=True)
S = C.WinDLL('shell32', use_last_error=True)
K = C.WinDLL('kernel32', use_last_error=True)
LRESULT = C.c_ssize_t
WNDPROC = C.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)


class WNDCLASS(C.Structure):
    _fields_ = [('style', W.UINT), ('lpfnWndProc', WNDPROC),
                ('cbClsExtra', C.c_int), ('cbWndExtra', C.c_int),
                ('hInstance', W.HINSTANCE), ('hIcon', W.HICON),
                ('hCursor', W.HANDLE), ('hbrBackground', W.HBRUSH),
                ('lpszMenuName', W.LPCWSTR), ('lpszClassName', W.LPCWSTR)]


class NOTIFYICONDATA(C.Structure):
    _fields_ = [('cbSize', W.DWORD), ('hWnd', W.HWND), ('uID', W.UINT),
                ('uFlags', W.UINT), ('uCallbackMessage', W.UINT),
                ('hIcon', W.HICON), ('szTip', W.WCHAR * 128),
                ('dwState', W.DWORD), ('dwStateMask', W.DWORD),
                ('szInfo', W.WCHAR * 256), ('uTimeoutOrVersion', W.UINT),
                ('szInfoTitle', W.WCHAR * 64), ('dwInfoFlags', W.DWORD),
                ('guidItem', C.c_byte * 16), ('hBalloonIcon', W.HICON)]


def signature(dll, name, restype, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = restype, args
    return fn


signature(K, 'GetModuleHandleW', W.HMODULE, W.LPCWSTR)
signature(K, 'CreateMutexW', W.HANDLE, C.c_void_p, W.BOOL, W.LPCWSTR)
signature(K, 'CloseHandle', W.BOOL, W.HANDLE)
signature(U, 'MessageBoxW', C.c_int, W.HWND, W.LPCWSTR, W.LPCWSTR, W.UINT)
signature(U, 'RegisterClassW', W.WORD, C.POINTER(WNDCLASS))
signature(U, 'CreateWindowExW', W.HWND, W.DWORD, W.LPCWSTR, W.LPCWSTR,
          W.DWORD, C.c_int, C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU,
          W.HINSTANCE, C.c_void_p)
signature(U, 'DefWindowProcW', LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
signature(U, 'DestroyWindow', W.BOOL, W.HWND)
signature(U, 'PostQuitMessage', None, C.c_int)
signature(U, 'GetMessageW', C.c_int, C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT)
signature(U, 'TranslateMessage', W.BOOL, C.POINTER(W.MSG))
signature(U, 'DispatchMessageW', LRESULT, C.POINTER(W.MSG))
signature(U, 'RegisterWindowMessageW', W.UINT, W.LPCWSTR)
signature(U, 'CreatePopupMenu', W.HMENU)
signature(U, 'AppendMenuW', W.BOOL, W.HMENU, W.UINT, C.c_size_t, W.LPCWSTR)
signature(U, 'DestroyMenu', W.BOOL, W.HMENU)
signature(U, 'GetCursorPos', W.BOOL, C.POINTER(W.POINT))
signature(U, 'SetForegroundWindow', W.BOOL, W.HWND)
signature(U, 'TrackPopupMenu', W.UINT, W.HMENU, W.UINT, C.c_int, C.c_int,
          C.c_int, W.HWND, C.c_void_p)
signature(U, 'PostMessageW', W.BOOL, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
signature(U, 'LoadImageW', W.HANDLE, W.HINSTANCE, W.LPCWSTR, W.UINT,
          C.c_int, C.c_int, W.UINT)
signature(U, 'DestroyIcon', W.BOOL, W.HICON)
signature(S, 'Shell_NotifyIconW', W.BOOL, W.DWORD, C.POINTER(NOTIFYICONDATA))

CALLBACK = 0x8001
TASKBAR_CREATED = U.RegisterWindowMessageW('TaskbarCreated')


class Tray:
    def __init__(self, url, listeners):
        self.listeners = listeners
        self.url = url
        self.proc = WNDPROC(self.window_proc)  # Keep callback alive.
        self.instance = K.GetModuleHandleW(None)
        self.icon = U.LoadImageW(None, str(ROOT / 'pace.ico'), 1, 0, 0, 0x10 | 0x40)
        if not self.icon:
            raise C.WinError(C.get_last_error())
        cls = WNDCLASS()
        cls.lpfnWndProc, cls.hInstance = self.proc, self.instance
        cls.hIcon, cls.lpszClassName = self.icon, 'PACETrayWindow'
        if not U.RegisterClassW(C.byref(cls)):
            raise C.WinError(C.get_last_error())
        self.hwnd = U.CreateWindowExW(0, cls.lpszClassName, 'PACE', 0,
                                     0, 0, 0, 0, None, None, self.instance, None)
        if not self.hwnd:
            raise C.WinError(C.get_last_error())
        self.notice = NOTIFYICONDATA()
        self.notice.cbSize = C.sizeof(NOTIFYICONDATA)
        self.notice.hWnd, self.notice.uID = self.hwnd, 1
        self.notice.uFlags = 1 | 2 | 4
        self.notice.uCallbackMessage = CALLBACK
        self.notice.hIcon, self.notice.szTip = self.icon, 'PACE — Open dashboard / Settings'
        if not S.Shell_NotifyIconW(0, C.byref(self.notice)):
            raise RuntimeError('Windows could not create the PACE tray icon.')

    def menu(self, hwnd):
        menu = U.CreatePopupMenu()
        try:
            U.AppendMenuW(menu, 0, 1, 'Open dashboard')
            U.AppendMenuW(menu, 0, 2, 'Open PACE folder')
            submenu=U.CreatePopupMenu()
            from server import VERSION
            from network import LABELS
            U.AppendMenuW(submenu, 2, 0, 'PACE26 · Version '+VERSION)
            for cmd,mode in [(11,'local'),(12,'lan'),(13,'tailscale')]:
                U.AppendMenuW(submenu, 8 if self.listeners.mode==mode else 0, cmd, LABELS[mode])
            U.AppendMenuW(submenu, 0, 14, 'Connection addresses / status')
            U.AppendMenuW(menu, 0x10, submenu, 'Settings')
            U.AppendMenuW(menu, 0x800, 0, None)
            U.AppendMenuW(menu, 0, 3, 'Exit PACE')
            point = W.POINT()
            U.GetCursorPos(C.byref(point))
            U.SetForegroundWindow(hwnd)
            chosen = U.TrackPopupMenu(menu, 0x100 | 0x2, point.x, point.y, 0, hwnd, None)
            if chosen == 1:
                webbrowser.open(self.url)
            elif chosen == 2:
                import os
                os.startfile(ROOT.parent)
            elif chosen in (11,12,13):
                try:
                    self.listeners.switch({11:'local',12:'lan',13:'tailscale'}[chosen])
                    U.MessageBoxW(hwnd,self.listeners.describe(),'PACE connection settings',0x40)
                except Exception as e: U.MessageBoxW(hwnd,str(e),'Connection mode unchanged',0x30)
            elif chosen == 14:
                U.MessageBoxW(hwnd,self.listeners.describe(),'PACE connection settings',0x40)
            elif chosen == 3:
                U.DestroyWindow(hwnd)
            U.PostMessageW(hwnd, 0, 0, 0)
        finally:
            U.DestroyMenu(menu)

    def window_proc(self, hwnd, message, wparam, lparam):
        try:
            if message == CALLBACK:
                if lparam == 0x202:  # Left button up.
                    webbrowser.open(self.url)
                elif lparam == 0x205:  # Right button up.
                    self.menu(hwnd)
                return 0
            if message == TASKBAR_CREATED and hasattr(self, 'notice'):
                S.Shell_NotifyIconW(0, C.byref(self.notice))
                return 0
            if message == 2:  # WM_DESTROY
                U.PostQuitMessage(0)
                return 0
            if message == 0x11:  # Windows ending this session.
                return 1
            if message == 0x16 and wparam:
                U.PostQuitMessage(0)
                return 0
        except Exception:
            logging.exception('Tray action failed')
        return U.DefWindowProcW(hwnd, message, wparam, lparam)

    def run(self):
        message = W.MSG()
        while True:
            result = U.GetMessageW(C.byref(message), None, 0, 0)
            if result == 0:
                break
            if result == -1:
                raise C.WinError(C.get_last_error())
            U.TranslateMessage(C.byref(message))
            U.DispatchMessageW(C.byref(message))

    def close(self):
        S.Shell_NotifyIconW(2, C.byref(self.notice))
        U.DestroyIcon(self.icon)


def main():
    mutex = K.CreateMutexW(None, False, 'Local\\PACE26TrayLauncher-' + __import__('hashlib').sha256(str(ROOT).encode()).hexdigest()[:12])
    already_running = C.get_last_error() == 183
    server = tray = thread = None
    try:
        if not mutex:
            raise C.WinError(C.get_last_error())
        if already_running:
            U.MessageBoxW(None, 'PACE is already running in the tray. Click its P icon near the clock to open it.', 'PACE', 0x40)
            return
        from logging.handlers import RotatingFileHandler
        from bootstrap import prepare_data
        prepare_data(DATA)
        DATA.mkdir(exist_ok=True)
        logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(
            DATA / 'pace-tray.log', maxBytes=1_000_000, backupCount=1, encoding='utf-8')])
        from server import Store, Server
        store = Store(DATA)
        from network import Listeners
        port=int(store.config.get('port',8765))
        url=f'http://127.0.0.1:{port}'
        Server.allow_reuse_address=False
        server=Listeners(store,Server)
        tray=Tray(url,server)
        server.stop_callback=lambda: U.PostMessageW(tray.hwnd,0x0010,0,0)
        server.restart_command=[sys.executable,str(ROOT/'tray.pyw')]
        desired=store.config.get('connection_mode','local')
        try:server.switch(desired)
        except ValueError as e:
            if desired=='local':raise
            server.switch('local')
            U.MessageBoxW(None,str(e)+'\n\nPACE started in This computer only mode.','PACE',0x30)
        webbrowser.open(url)
        tray.run()
    except Exception as error:
        logging.exception('PACE tray failed')
        U.MessageBoxW(None, str(error) + '\n\nSee data\\pace-tray.log or use START_PACE.cmd for troubleshooting.', 'PACE could not start', 0x10)
    finally:
        if tray:
            tray.close()
        if server:
            server.close()
        if mutex:
            K.CloseHandle(mutex)


if __name__ == '__main__':
    main()
