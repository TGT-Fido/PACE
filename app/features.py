"""PACE 5 local project management, search, snapshots and update staging."""
import base64, copy, hashlib, io, json, os, re, shutil, sqlite3, sys, threading, time, uuid, zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from urllib.request import urlopen, Request
sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
from pypdf import PdfReader

PRESETS = dict(zip(['Teal','Purple','Green','Blue','Orange','Pink','Yellow','Gray','Red','Light Green','Dark Blue','Cyan','White','Black','Rose Gold','Atomic Blue','Lavender','Mint','Coral','Amber','Magenta','Silver','Indigo','Lime'], ['#4db7c2','#a17cde','#75be8a','#689edd','#e4a46b','#dc86b1','#d5bd6a','#9ba4b4','#ef5350','#a5d66f','#244b91','#39cde0','#ffffff','#111111','#c58b86','#3232fa','#c0a6ee','#86dec2','#ff806c','#ffbf47','#d65cce','#c5cbd3','#6964d9','#c5df50']))
MAX_PDF = 75 * 1024 * 1024

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def safe_name(name):
    if not isinstance(name,str) or not name.strip() or len(name)>150 or name != name.strip() or name.endswith('.') or re.search(r'[<>:"/\\|?*\x00-\x1f]',name) or name.startswith(('.', '~', '$')) or name.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'{p}{n}' for p in ('COM','LPT') for n in range(1,10)]}:
        raise ValueError('Use a simple filename without slashes, reserved names or trailing spaces/dots')
    return name

def read_archive(path):
    """Validate every member before any extraction; limit expanded archive size."""
    z = zipfile.ZipFile(path)
    names=set(); total=0
    for f in z.infolist():
        p=PurePosixPath(f.filename)
        if '\\' in f.filename or p.is_absolute() or any(x in {'.','..'} for x in p.parts) or ':' in f.filename or (f.external_attr>>16)&0o170000 == 0o120000:
            z.close(); raise ValueError('Unsafe archive path')
        if f.filename.casefold() in names: z.close(); raise ValueError('Duplicate archive path')
        names.add(f.filename.casefold()); total+=f.file_size
        if total>8*1024**3: z.close(); raise ValueError('Backup expands beyond the 8 GB safety limit')
    return z

def https_bytes(url, limit):
    if not isinstance(url,str) or urlsplit(url).scheme!='https' or urlsplit(url).username or urlsplit(url).password:
        raise ValueError('Use an HTTPS release URL')
    with urlopen(Request(url,headers={'User-Agent':'PACE-Updater/5.0'}),timeout=30) as r:
        if urlsplit(r.url).scheme!='https': raise ValueError('Update redirected away from HTTPS')
        data=r.read(limit+1)
    if len(data)>limit: raise ValueError('Download exceeds size limit')
    return data

def extend(Base, root, version, atomic_json):
 class Store(Base):
    def __init__(self,data):
        super().__init__(data)
        self.state.setdefault('colors', {v:k for k,v in PRESETS.items()})
        self.state.setdefault('brightness',75)
        self.state.setdefault('uploads',{})
        self.state.setdefault('backup_path',str(self.data.parent.parent / (self.data.parent.name+'-Backups')))
        self.state.setdefault('update_url','')
        self.save()
        notes=self.data/'ReleaseNotes'; notes.mkdir(exist_ok=True)
        shipped=root/'release-notes'
        if shipped.exists():
            for f in shipped.glob('*.md'):
                target=notes/f.name
                if not target.exists(): shutil.copy2(f,target)
        self.index_lock=threading.Lock()
        self.index_status={'running':False,'done':0,'total':0,'errors':[]}
        self.last_index=0
        self.maintenance=False
        self.staged=None

    def scan(self):
        result=super().scan()
        result.update(colors=self.state.get('colors',{}),presets=PRESETS,brightness=self.state.get('brightness',75))
        for p in result['projects']:
            for f in p['files']: f.update(self.state.get('uploads',{}).get(p['id'],{}).get(f['name'],{}))
        return result

    def settings(self,body):
        kind=body.get('kind')
        if kind not in {'color','brightness','backup','update'}: return super().settings(body)
        with self.lock:
            if kind=='color':
                value=body.get('value','').lower(); name=body.get('name','').strip()
                if not re.fullmatch('#[0-9a-f]{6}',value) or not 1<=len(name)<=80: raise ValueError('Enter a color and a name (1–80 characters)')
                if any(n.casefold()==name.casefold() and c!=value for c,n in self.state['colors'].items()): raise ValueError('That name is already used for another color')
                self.state['colors'][value]=name
            elif kind=='brightness':
                value=body.get('value')
                if not isinstance(value,int) or not 0<=value<=100: raise ValueError('Brightness must be 0–100')
                self.state['brightness']=value
            elif kind=='backup':
                destination=self.backup_destination(body.get('path'))
                destination.mkdir(parents=True,exist_ok=True)
                self.state['backup_path']=str(destination)
            else:
                url=body.get('url','').strip()
                if url and (urlsplit(url).scheme!='https' or urlsplit(url).username or urlsplit(url).password): raise ValueError('Use an HTTPS manifest URL')
                self.state['update_url']=url
                self.staged=None
            self.save()

    def backup_destination(self,value=None):
        raw=value if value is not None else self.state['backup_path']
        if not isinstance(raw,str) or not Path(raw).is_absolute(): raise ValueError('Enter an absolute folder path on the PACE server')
        p=Path(raw).resolve()
        if Path(raw).is_symlink(): raise ValueError('Choose a real backup folder, not a symbolic link')
        for live in [root.parent.resolve(),self.data.resolve()]:
            if p==live or p.is_relative_to(live) or live.is_relative_to(p): raise ValueError('Choose a separate backup folder outside the PACE installation and data folders')
        return p

    def create_project(self,body):
        name=safe_name(body.get('name',''))
        with self.lock:
            self.scan()
            if any(f.name.casefold()==name.casefold() for f in self.projects.iterdir()): raise ValueError('A folder with that name already exists')
            folder=self.projects/name; folder.mkdir()
            self.scan()
            return next(p for p in self.scan()['projects'] if p['folder']==name)

    def upload(self,body):
        name=safe_name(body.get('name',''))
        if not name.lower().endswith('.pdf'): raise ValueError('Choose a PDF file')
        raw=base64.b64decode(body.get('data',''),validate=True)
        if not raw.startswith(b'%PDF-') or len(raw)>MAX_PDF: raise ValueError('Choose a valid PDF up to 75 MB')
        try:
            pdf=PdfReader(io.BytesIO(raw)); count=len(pdf.pages)
            if not count: raise ValueError('Empty PDF')
        except Exception as e: raise ValueError('PDF is damaged or password-protected; upload an unlocked PDF') from e
        note=body.get('note','')
        if not isinstance(note,str) or len(note)>4000: raise ValueError('Version notes must be under 4,000 characters')
        with self.lock:
            self.scan(); pid=body['id']; folder=self.paths.get(pid)
            if folder is None: raise ValueError('Project folder is missing')
            if any(f.name.casefold()==name.casefold() for f in folder.iterdir()): raise ValueError('That filename already exists. Rename the new version; existing PDFs are never overwritten.')
            target=folder/name
            with target.open('xb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
            self.state['uploads'].setdefault(pid,{})[name]={'uploaded_at':now(),'note':note}
            self.save(); self.scan()
        self.start_index(force=True)
        return {'ok':True,'name':name,'pages':count}

    def backup(self,mode='full'):
        if mode not in {'full','settings'}: raise ValueError('Choose full or settings-only backup')
        with self.lock:
            self.scan(); destination=self.backup_destination(); destination.mkdir(parents=True,exist_ok=True)
            name=f'PACE-{mode}-{datetime.now().strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:6]}.zip'
            target=destination/name; tmp=target.with_suffix('.partial')
            manifest={'format':'PACE-backup-1','mode':mode,'version':version,'created':now(),'files':{}}
            try:
                with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
                    for base,prefix in [(self.data,'data'),(root,'app')]:
                        for f in sorted(base.rglob('*')):
                            rel=f.relative_to(base)
                            if f.is_symlink() or any((base/Path(*rel.parts[:i])).is_symlink() for i in range(1,len(rel.parts))): raise ValueError('Backup stopped: symbolic links are not supported')
                            if not f.is_file() or '__pycache__' in rel.parts or 'cache' in rel.parts or f.suffix in {'.pyc','.tmp','.partial','.log'}: continue
                            if prefix=='data' and mode=='settings' and rel.parts[0]=='Projects' and f.name!='.pace-id.json': continue
                            b=f.read_bytes(); arc=prefix+'/'+rel.as_posix(); z.writestr(arc,b); manifest['files'][arc]=hashlib.sha256(b).hexdigest()
                    z.writestr('backup.json',json.dumps(manifest,indent=2))
                os.replace(tmp,target)
            finally:
                tmp.unlink(missing_ok=True)
            self.validate_backup(name)
            return {'name':name,'path':str(target),'mode':mode,'size':target.stat().st_size}

    def backup_info(self):
        destination=self.backup_destination()
        files=[]
        if destination.exists():
            for f in sorted(destination.glob('PACE-*.zip'),key=lambda p:p.stat().st_mtime,reverse=True):
                if not f.is_symlink(): files.append({'name':f.name,'size':f.stat().st_size})
        return {'path':str(destination),'backups':files,'update_url':self.state['update_url']}

    def backup_file(self,name):
        safe_name(name)
        if not name.startswith('PACE-') or not name.endswith('.zip'): raise ValueError('Choose a PACE backup')
        f=self.backup_destination()/name
        if f.is_symlink() or not f.is_file(): raise ValueError('Backup not found')
        return f

    def validate_backup(self,name):
        f=self.backup_file(name)
        with read_archive(f) as z:
            m=json.loads(z.read('backup.json'))
            if m.get('format')!='PACE-backup-1' or m.get('mode') not in {'full','settings'}: raise ValueError('Not a supported PACE backup')
            files=m.get('files',{})
            if set(z.namelist()) != set(files)|{'backup.json'}: raise ValueError('Backup manifest does not match its files')
            for n,h in files.items():
                if not n.startswith(('data/','app/')) or hashlib.sha256(z.read(n)).hexdigest()!=h: raise ValueError('Backup verification failed')
            dashboard=json.loads(z.read('data/dashboard.json'))
            if dashboard.get('schema')!=1 or not isinstance(dashboard.get('projects'),dict): raise ValueError('Invalid saved dashboard')
            return m

    def restore(self,name):
        """Restore data transactionally. App recovery is provided by the offline helper."""
        with self.lock:
            if self.index_status['running']: raise ValueError('Wait for PDF indexing to finish before restoring')
            manifest=self.validate_backup(name)
            safety=self.backup('full')
            stage=self.data.with_name(self.data.name+'.restore-'+uuid.uuid4().hex)
            previous=self.data.with_name(self.data.name+'.previous-'+uuid.uuid4().hex)
            try:
                if manifest['mode']=='settings': shutil.copytree(self.data,stage)
                else: stage.mkdir()
                with read_archive(self.backup_file(name)) as z:
                    for n in manifest['files']:
                        if n.startswith('data/'):
                            target=stage/n[5:]; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(z.read(n))
                # Keep server address and backup destination of this installation.
                atomic_json(stage/'config.json',self.config)
                s=json.loads((stage/'dashboard.json').read_text()); s['backup_path']=self.state['backup_path']; atomic_json(stage/'dashboard.json',s)
                shutil.rmtree(stage/'cache',ignore_errors=True)
                self.data.rename(previous)
                try:
                    stage.rename(self.data)
                    self.state=s
                    self.last_index=0
                    self.documents=json.loads(self.document_path.read_text()) if self.document_path.exists() else {'schema':1,'documents':{}}
                except Exception:
                    if self.data.exists(): shutil.rmtree(self.data)
                    previous.rename(self.data); raise
                shutil.rmtree(previous)
                return {'ok':True,'safety_backup':safety['name'],'message':'Data restored. Server address preserved. To restore the bundled app version too, use RECOVER_PACE.cmd.'}
            finally:
                if stage.exists(): shutil.rmtree(stage)

    def index_db(self):
        folder=self.data/'cache'; folder.mkdir(exist_ok=True)
        db=sqlite3.connect(folder/'search.sqlite',timeout=30)
        db.execute('CREATE TABLE IF NOT EXISTS docs (key TEXT PRIMARY KEY, signature TEXT, pages TEXT, error TEXT)')
        return db

    def start_index(self,force=False):
        with self.index_lock:
            if self.maintenance or self.index_status['running'] or (not force and time.monotonic()-self.last_index<15): return
            self.last_index=time.monotonic()
            self.index_status={'running':True,'done':0,'total':0,'errors':[]}
        def work():
            try:
                with self.lock:
                    cards=self.scan()['projects']
                    items=[(p['id']+'/'+f['name'],self.paths[p['id']]/f['name']) for p in cards if not p['missing'] for f in p['files']]
                self.index_status['total']=len(items)
                with self.index_db() as db:
                    keys=[]
                    for key,path in items:
                        keys.append(key)
                        try:
                            stat=path.stat(); sig=f'{stat.st_size}:{stat.st_mtime_ns}'
                            old=db.execute('SELECT signature FROM docs WHERE key=?',(key,)).fetchone()
                            if not old or old[0]!=sig:
                                pages=[]; error=''
                                try:
                                    pdf=PdfReader(path)
                                    if len(pdf.pages)>3000: raise ValueError('Over 3,000 pages; excluded from content search')
                                    pages=[(p.extract_text() or '')[:200000] for p in pdf.pages]
                                    if not any(t.strip() for t in pages): error='No searchable text (scan/image PDF); OCR is not included'
                                except Exception as e: error='Text unavailable: '+str(e)[:160]
                                db.execute('INSERT OR REPLACE INTO docs VALUES (?,?,?,?)',(key,sig,json.dumps(pages),error))
                                db.commit()
                        except OSError: pass
                        self.index_status['done']+=1
                    for key, in db.execute('SELECT key FROM docs').fetchall():
                        if key not in keys: db.execute('DELETE FROM docs WHERE key=?',(key,))
                    self.index_status['errors']=[{'file':k.split('/',1)[-1],'message':e} for k,e in db.execute("SELECT key,error FROM docs WHERE error!=''")]
            except Exception as e: self.index_status['errors']=[{'file':'Index','message':str(e)}]
            finally: self.index_status['running']=False
        threading.Thread(target=work,daemon=True,name='PACE PDF index').start()

    def search(self,q,mode):
        if not isinstance(q,str) or len(q)>200: raise ValueError('Search up to 200 characters')
        terms=q.casefold().split(); cards=self.scan()['projects']; hits=[]; ids=set()
        for p in cards:
            text=' '.join([str(p.get(k,'')) for k in ['name','summary','category','status','detail','priority','milestone','folder']]+p.get('badges',[])+[f['name'] for f in p['files']]).casefold()
            if all(t in text for t in terms): ids.add(p['id'])
        if mode=='contents' and terms:
            self.start_index()
            with self.index_db() as db:
                for key,pages in db.execute('SELECT key,pages FROM docs'):
                    pid,name=key.split('/',1)
                    if not any(p['id']==pid and any(f['name']==name for f in p['files']) for p in cards): continue
                    for page,text in enumerate(json.loads(pages),1):
                        folded=text.casefold()
                        if all(t in folded for t in terms):
                            ids.add(pid); pos=folded.find(terms[0]); start=max(0,pos-70)
                            if len(hits)<300: hits.append({'id':pid,'file':name,'page':page,'excerpt':' '.join(text[start:start+240].split())})
        return {'ids':list(ids),'hits':hits,'index':self.index_status}

    def release_notes(self):
        return [{'name':f.name,'text':f.read_text('utf-8')} for f in sorted((self.data/'ReleaseNotes').glob('*.md'),reverse=True) if not f.is_symlink()]

    def check_update(self):
        url=self.state['update_url']
        if not url: return {'configured':False,'message':'Hosting is not configured yet. Install this candidate manually; add your HTTPS release manifest later.'}
        m=json.loads(https_bytes(url,256000))
        if m.get('format')!='PACE-update-1' or not re.fullmatch(r'\d+\.\d+\.\d+',m.get('version','')) or not re.fullmatch('[a-fA-F0-9]{64}',m.get('sha256','')): raise ValueError('Invalid release manifest')
        if urlsplit(m.get('url','')).scheme!='https': raise ValueError('Release download must use HTTPS')
        newer=tuple(map(int,m['version'].split('.')))>tuple(map(int,version.split('.')))
        self.staged=m if newer else None
        return {'configured':True,'available':newer,'version':m['version'],'notes':m.get('notes',''),'message':'Update available' if newer else 'You are up to date'}

    def prepare_update(self):
        if not self.staged: raise ValueError('Check for updates first')
        m=copy.deepcopy(self.staged)
        raw=https_bytes(m['url'],150*1024*1024)
        if hashlib.sha256(raw).hexdigest().lower()!=m['sha256'].lower(): raise ValueError('Update checksum does not match; installation cancelled')
        work=self.backup_destination() / ('update-'+uuid.uuid4().hex); work.mkdir(parents=True)
        archive=work/'update.zip'; archive.write_bytes(raw)
        with read_archive(archive) as z:
            if 'app/server.py' not in z.namelist() or 'app/VERSION' not in z.namelist() or z.read('app/VERSION').decode().strip()!=m['version']: raise ValueError('Update package version does not match')
            if any(not n.startswith('app/') for n in z.namelist()): raise ValueError('Update packages may contain only the app folder')
            z.extractall(work/'new')
        backup=self.backup('full')
        return {'work':str(work),'backup':backup['path'],'version':m['version']}
 return Store
