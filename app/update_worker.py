"""Detached updater. Runs from the external backup folder, after PACE exits."""
import json, os, shutil, subprocess, sys, time, urllib.request
from pathlib import Path

def apply(work, app, data, command, url, expected):
    work,app,data=map(Path,(work,app,data)); old=work/'previous-app'; saved=work/'previous-data'
    # A complete copy permits rollback if a new app migrates data before failing.
    shutil.copytree(data,saved)
    shutil.copytree(app,old)
    try:
        shutil.rmtree(app)
        shutil.copytree(work/'new/app',app)
        process=subprocess.Popen(command)
        success=False
        for _ in range(45):
            time.sleep(1)
            if process.poll() is not None: break
            try:
                with urllib.request.urlopen(url+'/api/state',timeout=2) as r: state=json.load(r)
                if state.get('app')=='PACE' and state.get('version')==expected: success=True; break
            except Exception: pass
        if not success:
            if process.poll() is None: process.terminate(); process.wait(timeout=15)
            raise RuntimeError('Updated app did not pass its startup check')
        (work/'result.txt').write_text('Update completed: '+expected,encoding='utf-8')
    except Exception as error:
        if app.exists(): shutil.rmtree(app)
        shutil.copytree(old,app)
        if data.exists(): shutil.rmtree(data)
        shutil.copytree(saved,data)
        (work/'result.txt').write_text('Rolled back: '+str(error),encoding='utf-8')
        subprocess.Popen(command)
        raise

def main():
    job=json.loads(Path(sys.argv[1]).read_text()); pid=job['pid']
    for _ in range(120):
        if sys.platform=='win32':
            import ctypes
            k=ctypes.windll.kernel32
            k.OpenProcess.restype=ctypes.c_void_p
            k.CloseHandle.argtypes=[ctypes.c_void_p]
            handle=k.OpenProcess(0x1000,False,pid)
            if not handle: break
            k.CloseHandle(handle)
        else:
            try: os.kill(pid,0)
            except ProcessLookupError: break
        time.sleep(1)
    else: raise RuntimeError('PACE did not exit; update cancelled')
    apply(job['work'],job['app'],job['data'],job['command'],job['url'],job['version'])
if __name__=='__main__': main()
