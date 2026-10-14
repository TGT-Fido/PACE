import base64
import copy
import json
import http.client
import pathlib
import sys
import tempfile
import threading
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'app'))
from server import Store, Server, STATUSES, atomic_json


class OrganizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = pathlib.Path(self.temp.name)
        self.store = Store(self.data)
        self.folder = self.store.projects / 'Project'
        self.folder.mkdir()
        self.pid = self.store.scan()['projects'][0]['id']

    def tearDown(self):
        self.temp.cleanup()

    def test_migration_backup_and_confirmed_status_preserve_user_data(self):
        legacy = {'schema': 1, 'projects': {'id': {'name':'Example Project','category':'Technology','status':'Active','pin':'Old.pdf','summary':'My edit'}}, 'order':['id']}
        atomic_json(self.data/'dashboard.json', legacy)
        store = Store(self.data)
        self.assertEqual(json.loads((self.data/'dashboard.before-v4.json').read_text()), legacy)
        p = store.state['projects']['id']
        self.assertEqual((p['status'],p['detail'],p['pin'],p['summary']),('In progress','Active','Old.pdf','My edit'))
        store.state['projects']['id']['detail']='Custom detail';store.save()
        self.assertEqual(Store(self.data).state['projects']['id']['detail'],'Custom detail')

    def test_metadata_rename_new_pdf_and_restart_keep_badges_color_status(self):
        self.store.update({'id':self.pid,'changes':{'status':'Researching','badges':['Audio','D&D','Audio'],'color':'#123abc','detail':'Design chosen'}})
        self.folder.rename(self.folder.with_name('Renamed'))
        (self.folder.with_name('Renamed')/'Master_v1.10.pdf').write_bytes(b'%PDF')
        card=Store(self.data).scan()['projects'][0]
        self.assertEqual(card['id'],self.pid)
        self.assertEqual(card['badges'],['Audio','D&D'])
        self.assertEqual(card['color'],'#123abc')
        self.assertEqual(card['status'],'Researching')
        self.assertEqual(card['active']['name'],'Master_v1.10.pdf')

    def test_taxonomy_rename_delete_and_unused_entries_persist(self):
        self.store.settings({'kind':'category','action':'add','name':'Books'})
        self.store.settings({'kind':'badge','action':'add','name':'Audio'})
        self.store.update({'id':self.pid,'changes':{'category':'Books','badges':['Audio']}})
        self.store.settings({'kind':'category','action':'rename','name':'Books','new_name':'Reading'})
        self.store.settings({'kind':'badge','action':'rename','name':'Audio','new_name':'Listening'})
        card=self.store.scan()['projects'][0]
        self.assertEqual(card['category'],'Reading');self.assertEqual(card['badges'],['Listening'])
        self.store.settings({'kind':'category','action':'delete','name':'Reading'})
        self.store.settings({'kind':'badge','action':'delete','name':'Listening'})
        self.assertEqual(self.store.scan()['projects'][0]['category'],'Other')
        self.assertEqual(self.store.scan()['projects'][0]['badges'],[])
        self.store.settings({'kind':'badge','action':'add','name':'Unused'})
        self.assertIn('Unused',Store(self.data).scan()['badges'])

    def test_invalid_settings_and_metadata_do_not_change_saved_state(self):
        original=copy.deepcopy(self.store.state)
        for change in [{'status':'Stopped'},{'color':'url(evil)'},{'badges':'Audio'},{'badges':['']},{'detail':'a'*161}]:
            with self.assertRaises(ValueError):self.store.update({'id':self.pid,'changes':change})
        for body in [{'kind':'category','action':'delete','name':'Other'},{'kind':'background','action':'upload','data':base64.b64encode(b'<svg/>').decode()},{'kind':'badge','action':'add','name':' '}]:
            with self.assertRaises(ValueError):self.store.settings(body)
        self.assertEqual(self.store.state,original)

    def test_background_is_separate_asset_and_reset_preserves_original(self):
        raw=b'\x89PNG\r\n\x1a\nexample'
        self.store.settings({'kind':'background','action':'upload','data':base64.b64encode(raw).decode()})
        url=self.store.scan()['background']
        self.assertEqual((self.data/'backgrounds'/url.split('/')[-1]).read_bytes(),raw)
        self.assertEqual(Store(self.data).scan()['background'],url)
        self.store.settings({'kind':'background','action':'reset'})
        self.assertIsNone(self.store.scan()['background'])
        self.assertEqual((self.data/'backgrounds'/url.split('/')[-1]).read_bytes(),raw)

    def test_new_projects_are_planned_with_empty_badges(self):
        p=self.store.scan()['projects'][0]
        self.assertEqual(p['status'],'Planned');self.assertEqual(p['badges'],[])
        self.assertEqual(self.store.scan()['statuses'],STATUSES)

    def test_settings_http_guards_and_background_path_allowlist(self):
        self.store.config['allowed_hosts']=['pace.example.test']
        server=Server(('127.0.0.1',0),self.store)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(path, body=None, token=None, origin='https://pace.example.test', host='pace.example.test'):
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            headers={'Host':host,'Origin':origin}
            if token:headers['X-PACE-Token']=token
            conn.request('POST' if body else 'GET',path,json.dumps(body) if body else None,headers)
            response=conn.getresponse();content=response.read();status=response.status;conn.close()
            return status,content
        try:
            body={'kind':'badge','action':'add','name':'New badge'}
            self.assertEqual(request('/api/settings',body)[0],403)
            self.assertEqual(request('/api/settings',body,server.token,origin='https://evil.example')[0],403)
            self.assertEqual(request('/api/settings',body,server.token,host='evil.example')[0],403)
            self.assertEqual(request('/api/settings',body,server.token)[0],200)
            for path in ['/background/../config.json','/background/%2e%2e%2fconfig.json','/background/file.svg']:
                self.assertEqual(request(path)[0],400)
            raw=b'\x89PNG\r\n\x1a\nexample'
            self.store.settings({'kind':'background','action':'upload','data':base64.b64encode(raw).decode()})
            status,content=request(self.store.state['background'])
            self.assertEqual(status,200);self.assertEqual(content,raw)
        finally:server.shutdown();thread.join();server.server_close()


if __name__ == '__main__':unittest.main()
