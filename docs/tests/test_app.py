import json, pathlib, sys, tempfile, threading, unittest, urllib.request, urllib.error
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'app'))
from server import Store, Server, pdf_info

class PaceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.store=Store(self.root);self.folder=self.store.projects/'First';self.folder.mkdir()
 def tearDown(self): self.tmp.cleanup()
 def card(self): return self.store.scan()['projects'][0]
 def put(self,name): (self.folder/name).write_bytes(b'%PDF-1.4 test '+name.encode())
 def test_numeric_new_pdf_and_restart_pin(self):
  self.put('Master_v1.9.pdf');self.put('Master_v1.10.pdf');self.assertEqual(self.card()['active']['label'],'v1.10')
  self.store.update({'id':self.card()['id'],'changes':{'pin':'Master_v1.9.pdf'}})
  self.store=Store(self.root);self.assertEqual(self.card()['active']['label'],'v1.9')
  self.put('Master_v2.0.pdf');self.assertEqual(self.card()['active']['label'],'v1.9')
  self.store.update({'id':self.card()['id'],'changes':{'pin':None}});self.assertEqual(self.card()['active']['label'],'v2.0')
 def test_missing_pin(self):
  self.put('Master_v1.pdf');p=self.card();self.store.update({'id':p['id'],'changes':{'pin':'Master_v1.pdf'}});(self.folder/'Master_v1.pdf').unlink();p=self.card();self.assertIsNone(p['active']);self.assertIn('Pinned PDF missing',' '.join(p['warnings']));self.assertEqual(p['pin'],'Master_v1.pdf')
 def test_duplicate_and_supporting(self):
  self.put('Master_v1.0.pdf');self.put('Master_v1.0(1).pdf');self.put('receipt.pdf');self.assertIsNone(self.card()['active']);self.assertIn('Duplicate',' '.join(self.card()['warnings']))
  self.store.update({'id':self.card()['id'],'changes':{'pin':'Master_v1.0(1).pdf'}});self.assertEqual(self.card()['active']['name'],'Master_v1.0(1).pdf')
 def test_multiple_series_and_selection_retained(self):
  self.put('Master_v1.pdf');self.put('Invoice_v9.pdf');p=self.card();self.assertIsNone(p['active']);self.store.update({'id':p['id'],'changes':{'master_series':'master'}});self.assertEqual(self.card()['active']['name'],'Master_v1.pdf');self.put('Invoice_v10.pdf');self.assertEqual(self.card()['active']['name'],'Master_v1.pdf')
 def test_unversioned_ambiguous(self):
  self.put('notes.pdf');self.put('Master_v1_draft.pdf');p=self.card();self.assertIsNone(p['active']);self.assertTrue(any(f['ambiguous'] for f in p['files']));self.store.update({'id':p['id'],'changes':{'pin':'notes.pdf'}});self.assertEqual(self.card()['active']['name'],'notes.pdf')
 def test_discovery_rename_order_metadata(self):
  p=self.card();self.store.update({'id':p['id'],'changes':{'name':'Custom','status':'On hold','milestone':'Next'}});new=self.folder.with_name('Renamed');self.folder.rename(new)
  for i in range(16): (self.store.projects/f'Project {i:02}').mkdir()
  state=self.store.scan();self.assertEqual(len(state['projects']),17);self.assertEqual(state['projects'][0]['id'],p['id']);self.store.update({'id':p['id'],'move':1});self.store=Store(self.root);self.assertEqual(self.store.scan()['projects'][1]['name'],'Custom');self.assertEqual(self.store.scan()['projects'][1]['milestone'],'Next')
  new.rename(self.root/'Outside');self.assertTrue(self.store.scan()['projects'][1]['missing'])
 def test_hidden_symlink_duplicate_identity(self):
  p=self.card();(self.store.projects/'.hidden').mkdir();self.put('~temp.pdf');self.put('.hidden.pdf');(self.folder/'linked.pdf').symlink_to(self.root/'dashboard.json');self.assertEqual(self.card()['files'],[])
  copy=self.store.projects/'Second';copy.mkdir();(copy/'.pace-id.json').write_text((self.folder/'.pace-id.json').read_text());self.assertEqual(len(self.store.scan()['projects']),1);self.assertTrue(self.store.scan()['warnings'])
 def test_invalid_state_not_reset(self):
  self.card();self.store.path.write_text('{broken');self.assertRaises(ValueError,Store,self.root);self.assertEqual(self.store.path.read_text(),'{broken')
 def test_version_grammar(self):
  self.assertEqual(pdf_info('Project_v2.5_Interactive.pdf')['version'],[2,5]);self.assertEqual(pdf_info('A_v1.0.pdf')['version'],pdf_info('A_v1.pdf')['version']);self.assertIsNone(pdf_info('A_v1_v2.pdf')['version'])
 def test_http_special_names_and_path_safety(self):
  name='A & B #50% + café_v1.2.pdf';self.put(name);p=self.card();server=Server(('127.0.0.1',0),self.store);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
  try:
   with urllib.request.urlopen(base+p['active']['url']) as r:self.assertEqual(r.read(),(self.folder/name).read_bytes());self.assertEqual(r.headers['Content-Type'],'application/pdf')
   for path in ['/data/dashboard.json','/pdf/'+p['id']+'/%2e%2e%2fconfig.json','/pdf/'+p['id']+'/%5c..%5cconfig.json','/pdf/'+p['id']+'/%00.pdf','/pdf/'+p['id']+'/missing.pdf','/../server.py']:
    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+path)
    self.assertIn(e.exception.code,[400,404])
   req=urllib.request.Request(base+'/api/project',data=json.dumps({'id':p['id'],'changes':{'summary':'Saved'}}).encode(),headers={'Content-Type':'application/json'},method='POST')
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
   self.assertEqual(e.exception.code,403);req.add_header('X-PACE-Token',server.token)
   with urllib.request.urlopen(req) as r:self.assertEqual(r.status,200)
   self.assertEqual(Store(self.root).scan()['projects'][0]['summary'],'Saved')
  finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
