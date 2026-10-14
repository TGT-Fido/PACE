"""PACE local dashboard. Python standard library only; Python 3.10+."""
import argparse
import base64
import copy
import json
import hashlib
import mimetypes
import ipaddress
import os
import re
import secrets
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / 'VERSION').read_text('utf-8').strip()
STATUSES = ['Planned', 'Researching', 'In progress', 'On hold', 'Completed', 'Cancelled']

def short_name(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 80:
        raise ValueError('Use a name between 1 and 80 characters')
    return value.strip()

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def visible(path):
    return not path.name.startswith(('.', '~', '$')) and not (getattr(path.stat(), 'st_file_attributes', 0) & 2)

def pdf_info(name):
    stem = name[:-4]
    # Exactly one version token, at the end, optionally followed by _Interactive
    # and/or a Windows download-copy suffix. Other suffixes require manual pinning.
    matches = list(re.finditer(r'(?i)(?:^|[ _-])v(\d+(?:\.\d+)*)', stem))
    m = re.fullmatch(r'(?i)(.+?)[ _-]+v(\d+(?:\.\d+)*)(?:[ _-]+(Interactive))?(?:\s*\(\d+\))?', stem)
    if m and len(matches) == 1:
        version = tuple(int(n) for n in m[2].split('.'))
        while len(version) > 1 and version[-1] == 0:
            version = version[:-1]
        series = m[1].casefold() + ('_interactive' if m[3] else '')
        return {'name': name, 'series': series, 'version': list(version), 'label': 'v' + m[2], 'ambiguous': False}
    return {'name': name, 'series': None, 'version': None, 'label': 'Unrecognized version' if matches else 'Unversioned', 'ambiguous': bool(matches)}

class Store:
    def __init__(self, data):
        self.data = Path(data).resolve()
        self.projects = self.data / 'Projects'
        self.projects.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.path = self.data / 'dashboard.json'
        self.state = json.loads(self.path.read_text('utf-8')) if self.path.exists() else {'schema': 1, 'projects': {}, 'order': []}
        if self.state.get('schema') != 1 or not isinstance(self.state.get('projects'), dict) or not isinstance(self.state.get('order'), list):
            raise ValueError('Invalid dashboard.json. Restore a backup; settings have NOT been reset.')
        self.document_path = self.data / 'document_state.json'
        self.documents = json.loads(self.document_path.read_text('utf-8')) if self.document_path.exists() else {'schema': 1, 'documents': {}}
        if self.documents.get('schema') != 1 or not isinstance(self.documents.get('documents'), dict):
            raise ValueError('Invalid document_state.json. Restore a backup; PDF state has NOT been reset.')
        self.config_path = self.data / 'config.json'
        self.config = json.loads(self.config_path.read_text('utf-8')) if self.config_path.exists() else {'title': 'PACE', 'year': 2026, 'host': '127.0.0.1', 'port': 8765, 'page_size': 8}
        if not self.config_path.exists(): atomic_json(self.config_path, self.config)
        if self.state.get('features_version', 0) < 4:
            if self.path.exists():
                backup = self.path.with_name('dashboard.before-v4.json')
                if not backup.exists(): atomic_json(backup, self.state)
            self.state.setdefault('categories', [])
            self.state.setdefault('badges', [])
            self.state.setdefault('background', None)
            for meta in self.state['projects'].values():
                old = meta.get('status', 'Unconfirmed')
                if old not in STATUSES:
                    standard = next((s for s in STATUSES if s.casefold() == old.strip().casefold()), None)
                    meta.setdefault('detail', old if old != 'Unconfirmed' and not standard else '')
                    aliases = {'paused': 'On hold', 'parked': 'On hold', 'canceled': 'Cancelled', 'active': 'In progress', 'ongoing': 'In progress'}
                    meta['status'] = standard or aliases.get(old.casefold(), 'Planned')
                meta.setdefault('badges', [])
                meta.setdefault('color', None)
                meta.setdefault('detail', '')
            self.state['features_version'] = 4
            self.save()
        for key in ('categories', 'badges'):
            if not isinstance(self.state.get(key), list): raise ValueError('Invalid ' + key + ' settings; restore a backup')

    def save(self):
        atomic_json(self.path, self.state)

    def scan(self):
        with self.lock:
            before = json.dumps(self.state, sort_keys=True)
            paths, warnings = {}, []
            for folder in sorted(self.projects.iterdir(), key=lambda p: (p.name.casefold(), p.name)):
                if folder.is_symlink() or not folder.is_dir() or not visible(folder): continue
                marker = folder / '.pace-id.json'
                if marker.is_symlink():
                    warnings.append(f'{folder.name}: unsafe identity file; skipped.'); continue
                if marker.exists():
                    try:
                        pid = str(uuid.UUID(json.loads(marker.read_text('utf-8'))['id']))
                    except (ValueError, KeyError, TypeError):
                        warnings.append(f'{folder.name}: invalid .pace-id.json; restore it from backup.'); continue
                else:
                    pid = str(uuid.uuid4())
                    atomic_json(marker, {'id': pid})
                if pid in paths:
                    warnings.append(f'{folder.name}: duplicate identity; remove its .pace-id.json only if this is intentionally a NEW project copy.'); continue
                paths[pid] = folder
                if pid not in self.state['projects']:
                    self.state['projects'][pid] = {'name': folder.name, 'category': 'Other', 'status': 'Planned', 'detail': '', 'badges': [], 'color': None, 'priority': 'Unconfirmed', 'summary': 'Starter metadata — edit to describe this project.', 'milestone': 'Choose the next milestone.', 'source': 'Starter / unconfirmed', 'master_series': None, 'pin': None}
                    self.state['order'].append(pid)
                self.state['projects'][pid]['folder'] = folder.name
            cards = []
            for pid in self.state['order']:
                if pid not in self.state['projects']: continue
                meta = self.state['projects'][pid]
                if meta['category'] not in self.state['categories']: self.state['categories'].append(meta['category'])
                for badge in meta.get('badges', []):
                    if badge not in self.state['badges']: self.state['badges'].append(badge)
                folder = paths.get(pid)
                files = [] if folder is None else [pdf_info(p.name) for p in folder.iterdir() if p.is_file() and not p.is_symlink() and visible(p) and p.suffix.lower() == '.pdf']
                files.sort(key=lambda f: (f['name'].casefold(), f['name']))
                series = sorted(set(f['series'] for f in files if f['series']))
                selected = meta.get('master_series')
                notes = []
                if folder is None: notes.append('Project folder missing. Metadata retained; restore the folder with its identity file.')
                if not selected and len(series) == 1:
                    selected = series[0]
                    meta['master_series'] = selected
                candidates = [f for f in files if selected and f['series'] == selected]
                active = None
                if meta.get('pin'):
                    active = next((f for f in files if f['name'] == meta['pin']), None)
                    if not active: notes.append('Pinned PDF missing. Restore it or choose Automatic/latest; no fallback was substituted.')
                elif len(files) == 1:
                    active = files[0]
                elif candidates:
                    latest = max(tuple(f['version']) for f in candidates)
                    top = [f for f in candidates if tuple(f['version']) == latest]
                    if len(top) == 1: active = top[0]
                    else: notes.append('Duplicate latest version. Pin the intended file to resolve.')
                elif files:
                    notes.append('Choose a master series or pin a specific PDF in History.')
                if selected and not candidates and len(files) > 1: notes.append('Selected master series is missing; selection retained.')
                ambiguity_keys = []
                for f in files:
                    if f['ambiguous']:
                        stat = (folder / f['name']).stat()
                        signature = json.dumps([f['name'], stat.st_size, stat.st_mtime_ns])
                        ambiguity_keys.append(hashlib.sha256(signature.encode()).hexdigest())
                acknowledged = meta.get('acknowledged_ambiguities', [])
                new_ambiguities = [k for k in ambiguity_keys if k not in acknowledged]
                ambiguity_message = 'Some filenames have ambiguous versions; view or pin them explicitly.'
                if new_ambiguities: notes.append(ambiguity_message)
                groups = {}
                for f in candidates: groups.setdefault(tuple(f['version']), []).append(f)
                if any(len(v) > 1 for v in groups.values()) and not any('Duplicate' in n for n in notes): notes.append('Duplicate versions exist in history; filenames distinguish them.')
                for f in files: f['url'] = '/pdf/' + pid + '/' + quote(f['name'], safe='')
                files.sort(key=lambda f: (f['version'] is not None, tuple(f['version'] or [])), reverse=True)
                cards.append(dict(meta, id=pid, missing=folder is None, files=files, series=series, active=active, warnings=notes, ambiguity_keys=ambiguity_keys, new_ambiguities=len(new_ambiguities), ambiguity_message=ambiguity_message))
            if json.dumps(self.state, sort_keys=True) != before: self.save()
            self.paths = paths
            return {'app': 'PACE', 'projects': cards, 'warnings': warnings, 'config': self.config, 'version': VERSION,
                    'statuses': STATUSES, 'categories': self.state['categories'], 'badges': self.state['badges'],
                    'background': self.state.get('background')}

    def update(self, body):
        with self.lock:
            self.scan()
            pid = body['id']
            if pid not in self.state['projects']: raise ValueError('Unknown project')
            meta = self.state['projects'][pid]
            if body.get('dismiss_ambiguities') is True:
                snapshot = next(p for p in self.scan()['projects'] if p['id'] == pid)
                meta['acknowledged_ambiguities'] = snapshot['ambiguity_keys']
            elif 'move' in body:
                order = self.state['order']; i = order.index(pid)
                j = max(0, min(len(order)-1, i + int(body['move'])))
                order.insert(j, order.pop(i))
            else:
                changes = body.get('changes', {})
                allowed = {'name','category','status','priority','summary','milestone','master_series','pin','detail','badges','color'}
                if not isinstance(changes, dict) or set(changes) - allowed: raise ValueError('Invalid metadata fields')
                for k,v in changes.items():
                    if k == 'badges':
                        if not isinstance(v, list) or len(v) > 30: raise ValueError('Too many badges')
                        changes[k] = list(dict.fromkeys(short_name(b) for b in v))
                        continue
                    if v is not None and (not isinstance(v,str) or len(v)>2000): raise ValueError('Invalid field value')
                    if k not in {'master_series','pin','color'} and (v is None or (k in {'name','category','status'} and not v.strip())): raise ValueError('Name/category/status must be nonempty')
                    if k == 'status' and v not in STATUSES: raise ValueError('Choose a standard status')
                    if k == 'color' and v is not None and not re.fullmatch(r'#[0-9a-fA-F]{6}', v): raise ValueError('Invalid color')
                    if k == 'color' and v is not None: changes[k] = v.lower()
                    if k == 'category': changes[k] = short_name(v)
                    if k == 'detail' and len(v) > 160: raise ValueError('Detail must be concise')
                snapshot = next(p for p in self.scan()['projects'] if p['id']==pid)
                if changes.get('pin') and changes['pin'] not in [f['name'] for f in snapshot['files']]: raise ValueError('PDF no longer exists')
                if changes.get('master_series') and changes['master_series'] not in snapshot['series']: raise ValueError('Series no longer exists')
                meta.update(changes)
                if any(k in changes for k in {'name','category','status','priority','summary','milestone'}): meta['source']='Edited locally'
            self.save()

    def settings(self, body):
        """Atomic taxonomy/theme edits, separate from PDFs and network config."""
        with self.lock:
            self.scan()
            snapshot = copy.deepcopy(self.state)
            kind, action = body.get('kind'), body.get('action')
            if kind in {'category', 'badge'}:
                key = 'categories' if kind == 'category' else 'badges'
                name = short_name(body.get('name'))
                if kind == 'category' and name == 'Other' and action != 'add': raise ValueError('Other is the fallback category')
                values = snapshot[key]
                if action == 'add':
                    if len(values) >= 200: raise ValueError('Too many entries')
                    if any(v.casefold() == name.casefold() for v in values): raise ValueError('Name already exists')
                    values.append(name)
                elif action in {'rename', 'delete'}:
                    if name not in values: raise ValueError('Entry no longer exists')
                    target = short_name(body.get('new_name')) if action == 'rename' else 'Other'
                    if action == 'rename' and any(v.casefold() == target.casefold() and v != name for v in values): raise ValueError('Name already exists')
                    values.remove(name)
                    if action == 'rename': values.append(target)
                    elif kind == 'category' and target not in values: values.append(target)
                    for meta in snapshot['projects'].values():
                        if kind == 'category' and meta['category'] == name: meta['category'] = target
                        elif kind == 'badge': meta['badges'] = [target if b == name else b for b in meta.get('badges', []) if action != 'delete' or b != name]
                else: raise ValueError('Invalid action')
            elif kind == 'background':
                if action == 'reset': snapshot['background'] = None
                elif action == 'upload':
                    raw = base64.b64decode(body.get('data', ''), validate=True)
                    if not raw or len(raw) > 6_000_000: raise ValueError('Choose an image up to 6 MB')
                    if raw.startswith(b'\x89PNG\r\n\x1a\n'): ext = 'png'
                    elif raw.startswith(b'\xff\xd8\xff'): ext = 'jpg'
                    elif raw[:4] == b'RIFF' and raw[8:12] == b'WEBP': ext = 'webp'
                    else: raise ValueError('Choose PNG, JPEG or WebP')
                    assets = self.data / 'assets'
                    if assets.is_symlink(): raise ValueError('Unsafe assets folder')
                    assets.mkdir(exist_ok=True)
                    name = str(uuid.uuid4()) + '.' + ext
                    tmp = assets / (name + '.tmp')
                    with tmp.open('wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
                    os.replace(tmp, assets / name)
                    snapshot['background'] = '/background/' + name
                else: raise ValueError('Invalid action')
            else: raise ValueError('Invalid setting')
            atomic_json(self.path, snapshot)
            self.state = snapshot

    def document_file(self, pid, name):
        """Resolve an exact scanned PDF, never a caller-supplied filesystem path."""
        if not isinstance(name, str) or '/' in name or '\\' in name or '\x00' in name:
            raise ValueError('Invalid filename')
        card = next((p for p in self.scan()['projects'] if p['id'] == pid), None)
        if not card or name not in [f['name'] for f in card['files']]:
            raise FileNotFoundError('PDF not found')
        file = self.paths[pid] / name
        if file.is_symlink() or not file.resolve().is_relative_to(self.projects):
            raise ValueError('Unsafe path')
        content = file.read_bytes()
        fingerprint = hashlib.sha256(content).hexdigest()
        key = hashlib.sha256(json.dumps([pid, name, fingerprint]).encode()).hexdigest()
        return content, fingerprint, key

    def document_state(self, pid, name):
        with self.lock:
            _, fingerprint, key = self.document_file(pid, name)
            saved = self.documents['documents'].get(key, {})
            return {'fingerprint': fingerprint, 'revision': saved.get('revision', 0), 'values': saved.get('values', {})}

    def save_document_state(self, body):
        with self.lock:
            _, fingerprint, key = self.document_file(body['id'], body['file'])
            current = self.documents['documents'].get(key, {})
            if body.get('fingerprint') != fingerprint or body.get('revision') != current.get('revision', 0):
                return None  # file changed or another device saved first
            values = body.get('values')
            if not isinstance(values, dict) or len(values) > 10000:
                raise ValueError('Invalid form state')
            clean = {}
            for field, data in values.items():
                if not isinstance(field, str) or len(field) > 256 or not isinstance(data, dict) or set(data) != {'value'}:
                    raise ValueError('Invalid form field')
                value = data['value']
                if not isinstance(value, (bool, str, list)) or (isinstance(value, str) and len(value) > 20000):
                    raise ValueError('Invalid form value')
                if isinstance(value, list) and (len(value) > 1000 or any(not isinstance(v, str) or len(v) > 2000 for v in value)):
                    raise ValueError('Invalid form options')
                clean[field] = {'value': value}
            revision = current.get('revision', 0) + 1
            updated = dict(self.documents['documents'])
            updated[key] = {'project_id': body['id'], 'file': body['file'], 'fingerprint': fingerprint, 'revision': revision, 'values': clean}
            snapshot = {'schema': 1, 'documents': updated}
            atomic_json(self.document_path, snapshot)
            self.documents = snapshot
            return {'revision': revision}

from features import extend
Store = extend(Store, ROOT, VERSION, atomic_json)
from multiview import extend as extend_views
Store = extend_views(Store, atomic_json)
from workspace import extend as extend_workspace
Store = extend_workspace(Store, atomic_json)
from v7 import extend as extend_v7, safe_image
Store = extend_v7(Store, atomic_json)

class Server(ThreadingHTTPServer):
    daemon_threads = False
    def __init__(self, address, store):
        self.store = store
        self.stop_callback = self.shutdown
        self.restart_command = None
        self.token = secrets.token_urlsafe(32)
        super().__init__(address, Handler)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def send_bytes(self, body, mime, status=200):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; worker-src 'self' blob:; img-src 'self' data: blob:; font-src 'self' data:; object-src 'none'; frame-ancestors 'self'")
        self.end_headers()
        if self.command != 'HEAD': self.wfile.write(body)
    def json(self, obj, status=200): self.send_bytes(json.dumps(obj, ensure_ascii=False).encode(), 'application/json; charset=utf-8', status)
    def do_HEAD(self): self.do_GET()
    def valid_host(self):
        try:
            host = urlsplit('http://' + self.headers.get('Host', '')).hostname
            bound = self.server.server_address[0]
            allowed = self.server.store.config.get('allowed_hosts', [])
            if not isinstance(allowed, list): allowed = []
            allowed = {h.lower() for h in allowed if isinstance(h, str)}
            return host in {bound, 'localhost', '127.0.0.1'} or host in allowed or (bound == '0.0.0.0' and bool(ipaddress.ip_address(host)))
        except ValueError: return False
    def do_GET(self):
        if not self.valid_host(): self.json({'error':'Unrecognized host; use the configured IP address'},403); return
        try:
            path = urlsplit(self.path).path
            if path == '/api/images':
                query=parse_qs(urlsplit(self.path).query)
                self.json(self.server.store.images(query.get('kind',['background'])[0])); return
            if path.startswith(('/background/','/icon/')):
                kind, encoded = path.strip('/').split('/',1)
                root=self.server.store.data/('backgrounds' if kind=='background' else 'icons')
                f=safe_image(root,unquote(encoded,errors='strict'))
                self.send_bytes(f.read_bytes(),mimetypes.guess_type(f.name)[0]); return
            if path == '/api/state':
                self.json(dict(self.server.store.scan(), token=self.server.token)); return
            if path == '/api/document':
                query = parse_qs(urlsplit(self.path).query)
                self.json(self.server.store.document_state(query['id'][0], query['file'][0])); return
            if path == '/api/search':
                query = parse_qs(urlsplit(self.path).query)
                self.json(self.server.store.search(query.get('q',[''])[0],query.get('mode',['overview'])[0])); return
            if path == '/api/releases':
                self.json(self.server.store.release_notes()); return
            if path == '/api/storage':
                self.json(self.server.store.storage_info()); return
            if path == '/api/backups':
                self.json(self.server.store.backup_info()); return
            if path == '/api/backup-download':
                query = parse_qs(urlsplit(self.path).query)
                f = self.server.store.backup_file(query['name'][0])
                self.send_bytes(f.read_bytes(),'application/zip'); return
            static = {'/v7.css':'v7.css','/hdr.js':'hdr.js','/workspace.js':'workspace.js','/workspace.css':'workspace.css','/maps.js':'maps.js','/maps.css':'maps.css','/':'index.html','/app.js':'app.js','/viewer.js':'viewer.js','/style.css':'style.css','/hexagons.svg':'hexagons.svg'}
            if path in static:
                f = ROOT/'static'/static[path]
                self.send_bytes(f.read_bytes(), {'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8','svg':'image/svg+xml'}[f.suffix[1:]]); return
            if path.startswith('/vendor/pdfjs/'):
                relative = unquote(path[len('/vendor/pdfjs/'):], errors='strict')
                if any(x in relative for x in ('\\', '\x00')) or any(x in {'.', '..'} for x in relative.split('/')):
                    raise ValueError('Invalid asset path')
                base = ROOT/'static/vendor/pdfjs'
                asset = base/relative
                if not asset.resolve().is_relative_to(base) or asset.is_symlink() or not asset.is_file():
                    self.json({'error':'Asset not found'},404); return
                mime = 'text/javascript' if asset.suffix == '.mjs' else mimetypes.guess_type(asset.name)[0] or 'application/octet-stream'
                self.send_bytes(asset.read_bytes(), mime); return
            parts = path.split('/')
            if len(parts)==4 and parts[1]=='pdf':
                pid, name = parts[2], unquote(parts[3], errors='strict')
                if '/' in name or '\\' in name or '\x00' in name or name in {'.','..'}: raise ValueError('Invalid filename')
                with self.server.store.lock:
                    state = self.server.store.scan()
                    card = next((p for p in state['projects'] if p['id']==pid), None)
                    if not card or name not in [f['name'] for f in card['files']]: self.json({'error':'PDF not found'},404); return
                    folder = self.server.store.paths[pid]
                    f = folder/name
                    if f.is_symlink() or not f.resolve().is_relative_to(self.server.store.projects): raise ValueError('Unsafe path')
                    content = f.read_bytes()
                self.send_bytes(content,'application/pdf'); return
            self.json({'error':'Not found'},404)
        except FileNotFoundError: self.json({'error':'PDF not found'},404)
        except (ValueError, UnicodeError, KeyError): self.json({'error':'Malformed request'},400)
        except OSError: self.json({'error':'File unavailable; refresh and retry'},409)
    def do_POST(self):
        if not self.valid_host(): self.json({'error':'Unrecognized host'},403); return
        if self.path not in {'/api/delete-project', '/api/project', '/api/document', '/api/settings','/api/create','/api/upload','/api/backup','/api/restore','/api/update-check','/api/update-install','/api/visual'}: self.json({'error':'Not found'},404); return
        # A per-process token prevents cross-origin form writes and blind requests.
        if not secrets.compare_digest(self.headers.get('X-PACE-Token',''), self.server.token): self.json({'error':'Refresh the dashboard before saving'},403); return
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'): self.json({'error':'Wrong origin'},403); return
        try:
            size = int(self.headers.get('Content-Length','0'))
            limit = 106_000_000 if self.path == '/api/upload' else 34_000_000 if self.path == '/api/settings' else 1_000_000
            if not 0<size<=limit: raise ValueError('Request too large or empty')
            body = json.loads(self.rfile.read(size))
            with self.server.store.lock:
                if self.server.store.maintenance: raise ValueError('An update is in progress; try again after restart')
                if self.path == '/api/delete-project':
                    self.server.store.delete_project(body);self.json({'ok':True});return
                if self.path == '/api/visual':
                    self.json(self.server.store.visual_update(body)); return
                if self.path == '/api/create':
                    self.json(self.server.store.create_project(body)); return
                if self.path == '/api/upload':
                    self.json(self.server.store.upload(body)); return
                if self.path == '/api/backup':
                    self.json(self.server.store.backup(body.get('mode','full'))); return
                if self.path == '/api/restore':
                    self.json(self.server.store.restore(body['name'])); return
                if self.path == '/api/update-check':
                    self.json(self.server.store.check_update()); return
                if self.path == '/api/update-install':
                    import subprocess, sys, shutil
                    with self.server.store.lock:
                        if self.server.store.index_status['running']: raise ValueError('Wait for indexing to finish before updating')
                        self.server.store.maintenance = True
                        try:
                            job=self.server.store.prepare_update()
                            job.update(pid=os.getpid(),app=str(ROOT),data=str(self.server.store.data),
                                command=self.server.restart_command or [sys.executable,str(ROOT/'server.py'),'--data',str(self.server.store.data)],
                                url='http://127.0.0.1:'+str(self.server.server_address[1]))
                            if self.server.server_address[0] not in ('0.0.0.0','127.0.0.1'):
                                job['url']='http://'+self.server.server_address[0]+':'+str(self.server.server_address[1])
                            work=Path(job['work']); atomic_json(work/'job.json',job)
                            shutil.copy2(ROOT/'update_worker.py',work/'update_worker.py')
                            subprocess.Popen([sys.executable,str(work/'update_worker.py'),str(work/'job.json')],
                                creationflags=(0x00000008 | 0x00000200) if sys.platform=='win32' else 0,
                                start_new_session=sys.platform!='win32')
                        except Exception:
                            self.server.store.maintenance=False; raise
                    self.json({'ok':True,'message':'Backup complete. Installing and restarting PACE. Reload this page shortly.'})
                    threading.Timer(1,self.server.stop_callback).start(); return
                if self.path == '/api/settings':
                    self.server.store.settings(body)
                    self.json({'ok':True})
                elif self.path == '/api/document':
                    result = self.server.store.save_document_state(body)
                    if result is None:
                        self.json({'error':'This PDF or its saved state changed. Reload the document before saving again.'},409)
                    else: self.json(result)
                else:
                    self.server.store.update(body)
                    self.json({'ok':True})
        except FileNotFoundError: self.json({'error':'PDF no longer exists'},404)
        except (ValueError, KeyError, TypeError) as e: self.json({'error':str(e) or 'Invalid request'},400)
        except OSError: self.json({'error':'Could not save or download. Check permissions, disk space and network.'},500)
        except Exception as e:
            self.json({'error':'Operation failed: '+str(e)[:200]},400)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', default=str(ROOT.parent/'data'))
    parser.add_argument('--host'); parser.add_argument('--port',type=int)
    parser.add_argument('--open',action='store_true')
    args = parser.parse_args()
    from bootstrap import prepare_data
    prepare_data(args.data)
    store = Store(args.data)
    host, port = args.host or store.config['host'], args.port or store.config['port']
    server = Server((host,port), store)
    import sys
    server.restart_command=[sys.executable,str(ROOT/'server.py'),'--data',str(store.data),'--host',host,'--port',str(port)]
    url = f'http://{host if host not in ("0.0.0.0", "::") else "127.0.0.1"}:{port}'
    print(f'PACE {VERSION} running at {url}\nData: {store.data}\nKeep this window open. Ctrl+C stops the app.', flush=True)
    if args.open: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == '__main__': main()
