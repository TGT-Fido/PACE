"""PACE 7 image storage, saved appearance, and project lifecycle."""
import base64, copy, hashlib, os, re, shutil, uuid
from pathlib import Path
from urllib.parse import quote, unquote

ICONS = ['D&D','Home','Smart Home','Cars','Audio','Learning','Technology','Music','Travel','Art','Fitness','Work','Nature','Science','Camera','Coffee']

def safe_image(root, name):
    if not isinstance(name,str) or Path(name).name != name or any(x in name for x in ['/', '\\', '\x00']) or Path(name).suffix.lower() not in {'.png','.jpg','.jpeg','.webp'}:
        raise ValueError('Choose a PNG, JPEG or WebP image')
    p=root/name
    if root.is_symlink() or p.is_symlink() or not p.resolve().is_relative_to(root.resolve()): raise ValueError('Unsafe image path')
    return p

def extend(Base, atomic_json):
 class Store(Base):
    def __init__(self,data):
        super().__init__(data)
        self._migrate_v7()

    def restore(self,name):
        result=super().restore(name)
        self._migrate_v7()
        return result

    def _migrate_v7(self):
        old=self.data/'assets'; new=self.data/'backgrounds'
        if old.is_symlink() or new.is_symlink(): raise ValueError('Image folders must not be links')
        new.mkdir(exist_ok=True); (self.data/'icons').mkdir(exist_ok=True)
        # Keep old files until the new references have been saved successfully.
        if old.is_dir():
            moved=[]
            for p in old.iterdir():
                if not p.is_file() or p.is_symlink() or p.suffix.lower() not in {'.png','.jpg','.jpeg','.webp'}: continue
                dest=new/p.name
                if dest.exists() and dest.read_bytes()!=p.read_bytes():
                    dest=new/(hashlib.sha256(p.read_bytes()).hexdigest()+p.suffix.lower())
                if not dest.exists(): shutil.copy2(p,dest)
                if self.state.get('background')=='/background/'+p.name: self.state['background']='/background/'+quote(dest.name,safe='')
                moved.append(p)
            self.save()
            for p in moved:p.unlink()
            if not list(old.iterdir()):old.rmdir()
        prefs=self.state.setdefault('preferences',{})
        prefs.setdefault('rendering','legacy');prefs.setdefault('map_size','expanded');prefs.setdefault('map_title','PACE')
        self.save()

    def images(self,kind):
        root=self.data/('backgrounds' if kind=='background' else 'icons')
        return [{'name':p.name,'url':'/'+kind+'/'+quote(p.name,safe='')} for p in sorted(root.iterdir(),key=lambda p:p.name.casefold()) if p.is_file() and not p.is_symlink() and p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}]

    def scan(self):
        result=super().scan()
        result['custom_theme']=copy.deepcopy(self.state.get('custom_theme'))
        return result

    def image_upload(self,body,kind):
        raw=base64.b64decode(body.get('data',''),validate=True)
        if not raw or len(raw)>25_000_000:raise ValueError('Choose an image up to 25 MB')
        if raw.startswith(b'\x89PNG\r\n\x1a\n'):ext='.png'
        elif raw.startswith(b'\xff\xd8\xff'):ext='.jpg'
        elif raw[:4]==b'RIFF' and raw[8:12]==b'WEBP':ext='.webp'
        else:raise ValueError('Choose PNG, JPEG or WebP')
        root=self.data/('backgrounds' if kind=='background' else 'icons')
        if root.is_symlink():raise ValueError('Unsafe image folder')
        digest=hashlib.sha256(raw).hexdigest()
        for p in root.iterdir():
            if p.is_file() and not p.is_symlink() and p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'} and p.stat().st_size==len(raw) and hashlib.sha256(p.read_bytes()).hexdigest()==digest:
                return '/'+kind+'/'+quote(p.name,safe='')
        stem=re.sub(r'[^A-Za-z0-9 _-]','',Path(str(body.get('name','Image'))).stem).strip()[:70] or 'Image'
        name=stem+ext
        if (root/name).exists():name=stem+'-'+digest[:10]+ext
        p=safe_image(root,name); tmp=p.with_suffix(p.suffix+'.tmp')
        with tmp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
        return '/'+kind+'/'+quote(name,safe='')

    def settings(self,body):
        kind=body.get('kind')
        if kind not in {'background','icon','v7','custom-theme'}:return super().settings(body)
        with self.lock:
            if kind=='background':
                action=body.get('action')
                if action=='reset':self.state['background']=None
                elif action=='upload':self.state['background']=self.image_upload(body,'background')
                elif action=='select':
                    name=body.get('name');p=safe_image(self.data/'backgrounds',name)
                    if not p.is_file():raise ValueError('Background no longer exists')
                    self.state['background']='/background/'+quote(name,safe='')
                else:raise ValueError('Unknown background action')
            elif kind=='icon':
                pid=body.get('id')
                if pid not in self.state['projects']:raise ValueError('Project no longer exists')
                if body.get('action')=='upload':value=self.image_upload(body,'icon')
                else:
                    value=body.get('value')
                    if value is not None and value not in ICONS:
                        if not isinstance(value,str) or not value.startswith('/icon/'):raise ValueError('Unknown icon')
                        if not safe_image(self.data/'icons',unquote(value[6:])).is_file():raise ValueError('Icon no longer exists')
                self.state['projects'][pid]['icon']=value
            elif kind=='custom-theme':
                if body.get('action')=='save':
                    self.state['custom_theme']={'theme':self.state.get('preferences',{}).get('theme','dark'),'background':self.state.get('background'),'brightness':self.state.get('brightness',100)}
                elif body.get('action')=='apply':
                    preset=self.state.get('custom_theme')
                    if not preset:raise ValueError('Save a Custom preset first')
                    self.state.setdefault('preferences',{})['theme']=preset['theme']
                    self.state.update(background=preset['background'],brightness=preset['brightness'])
                else:raise ValueError('Unknown preset action')
            else:
                values=body.get('values',{})
                if not isinstance(values,dict) or set(values)-{'rendering','map_size','map_title'}:raise ValueError('Invalid settings')
                if 'rendering' in values and values['rendering'] not in {'legacy','hdr'}:raise ValueError('Invalid renderer')
                if 'map_size' in values and values['map_size'] not in {'centered','expanded'}:raise ValueError('Invalid map size')
                if 'map_title' in values and (not isinstance(values['map_title'],str) or not 1<=len(values['map_title'].strip())<=80):raise ValueError('Use a title of 1–80 characters')
                self.state.setdefault('preferences',{}).update(values)
            self.save()

    def delete_project(self,body):
        with self.lock:
            self.scan();pid=body.get('id');meta=self.state['projects'].get(pid)
            if not meta or body.get('confirm_name')!=meta['name']:raise ValueError('Confirm the current project name')
            folder=self.projects/meta['folder']
            if folder.is_symlink() or getattr(folder,'is_junction',lambda:False)() or folder.parent!=self.projects or not folder.resolve().is_relative_to(self.projects):raise ValueError('Unsafe project folder')
            # Reject nested reparse points before any destructive operation.
            if folder.exists():
                for root,dirs,files in os.walk(folder,followlinks=False):
                    for name in dirs+files:
                        p=Path(root)/name
                        if p.is_symlink() or getattr(p,'is_junction',lambda:False)():raise ValueError('Remove linked files/folders before deleting this project')
            before=copy.deepcopy(self.state); docs=copy.deepcopy(self.documents)
            quarantine=self.data/('.delete-'+uuid.uuid4().hex)
            if folder.exists():folder.rename(quarantine)
            try:
                del self.state['projects'][pid]
                self.state['order']=[x for x in self.state['order'] if x!=pid]
                if self.state.get('card_pages') is not None:self.state['card_pages']=[[x for x in page if x!=pid] for page in self.state['card_pages']]
                self.state['order_revision']=self.state.get('order_revision',0)+1
                self.state.get('uploads',{}).pop(pid,None)
                visual=self.state.get('visual',{});visual['parents']={k:v for k,v in visual.get('parents',{}).items() if k!=pid and v!=pid}
                visual['links']=[x for x in visual.get('links',[]) if x.get('from')!=pid and x.get('to')!=pid]
                visual['revision']=visual.get('revision',0)+1
                for layout in visual.get('layouts',{}).values():
                    layout.get('positions',{}).pop(pid,None);layout['collapsed']=[x for x in layout.get('collapsed',[]) if x!=pid]
                    if layout.get('focus')==pid:layout['focus']='root'
                self.documents['documents']={k:v for k,v in self.documents['documents'].items() if v.get('project_id')!=pid}
                atomic_json(self.document_path,self.documents);self.save()
            except Exception:
                self.state=before;self.documents=docs
                atomic_json(self.document_path,docs)
                if quarantine.exists():quarantine.rename(folder)
                raise
            if quarantine.exists():
                try:shutil.rmtree(quarantine)
                except OSError:raise ValueError('Project removed from dashboard, but some files are locked. Close PDF programs; residual files remain in '+quarantine.name)
            self.last_index=0
 return Store
