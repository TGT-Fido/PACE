"""Offline recovery: close PACE first, then run with Python 3.10+."""
import hashlib,json,os,shutil,socket,sys,uuid,zipfile
from pathlib import Path,PurePosixPath

def recover(backup,installation):
    root=Path(installation).resolve(); archive=Path(backup).resolve()
    if archive.is_relative_to(root): raise ValueError('Use a backup outside the PACE installation')
    config=root/'data/config.json'
    valid_config=False
    try:
        c=json.loads(config.read_text()); valid_config=isinstance(c,dict) and isinstance(c.get('port'),int) and isinstance(c.get('host'),str)
    except (OSError,ValueError): c={}
    if valid_config:
        host=c.get('host','127.0.0.1')
        try:
            with socket.create_connection(('127.0.0.1' if host=='0.0.0.0' else host,c.get('port',8765)),timeout=1):
                raise ValueError('PACE or another server is still running on this port. Exit PACE first.')
        except OSError: pass
    work=root.parent/('PACE-recovery-'+uuid.uuid4().hex); work.mkdir()
    old=work/'previous'; old.mkdir(); stage=work/'restored'; stage.mkdir()
    try:
        with zipfile.ZipFile(archive) as z:
            m=json.loads(z.read('backup.json'))
            if m.get('format')!='PACE-backup-1' or m.get('mode') not in {'full','settings'}: raise ValueError('Unsupported backup')
            files=m['files']; names=set(); total=0
            if set(z.namelist())!=set(files)|{'backup.json'}: raise ValueError('Manifest mismatch')
            for item in z.infolist():
                n=item.filename;p=PurePosixPath(n);total+=item.file_size
                if n.casefold() in names or p.is_absolute() or '..' in p.parts or '\\' in n or ':' in n or (item.external_attr>>16)&0o170000==0o120000 or total>8*1024**3: raise ValueError('Unsafe archive')
                names.add(n.casefold())
            if m['mode']=='settings' and (root/'data').exists(): shutil.copytree(root/'data',stage/'data')
            for n,h in files.items():
                if not n.startswith(('data/','app/')): raise ValueError('Unexpected backup file')
                b=z.read(n)
                if hashlib.sha256(b).hexdigest()!=h: raise ValueError('Damaged backup: '+n)
                f=stage/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b)
            if not (stage/'app/server.py').exists() or not (stage/'data/dashboard.json').exists(): raise ValueError('Incomplete backup')
            if valid_config: shutil.copy2(config,stage/'data/config.json')
        moved=[]; installed=[]
        try:
            for name in ['app','data']:
                if (root/name).exists(): (root/name).rename(old/name);moved.append(name)
                (stage/name).rename(root/name);installed.append(name)
        except Exception:
            for name in installed: shutil.rmtree(root/name)
            for name in moved: (old/name).rename(root/name)
            raise
        return str(old)
    finally:
        if stage.exists(): shutil.rmtree(stage)

if __name__=='__main__':
    try:
        archive=sys.argv[1] if len(sys.argv)>1 else input('Full path to backup ZIP: ').strip().strip('"')
        target=Path(__file__).resolve().parent
        if input('PACE must be closed. Restore app and data in '+str(target)+'? Type RESTORE: ')!='RESTORE': raise SystemExit('Cancelled')
        previous=recover(archive,target)
        print('Recovered. Your pre-recovery files are retained at '+previous+'\nStart PACE normally.')
    except Exception as e: print('Recovery failed: '+str(e));sys.exit(1)
