import copy,json,pathlib,socket,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'app'))
from server import Store,atomic_json
class V65Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.s=Store(self.root/'install/data');self.a=self.s.create_project({'name':'Project A'})['id'];self.b=self.s.create_project({'name':'Project B'})['id'];self.ids=[self.a,self.b]
 def tearDown(self):self.tmp.cleanup()
 def project(self):return next(p for p in self.s.scan()['projects'] if p['id']==self.a)
 def pdf(self,name):(self.s.projects/'Project A'/name).write_bytes(b'%PDF-test')
 def reorder(self,order,pages=None,revision=None):self.s.settings({'kind':'reorder','order':order,'pages':pages,'revision':self.s.scan()['order_revision'] if revision is None else revision})
 def test_single_pdf_and_missing_pin(self):
  self.pdf('notes.pdf');self.assertEqual(self.project()['active']['name'],'notes.pdf')
  self.pdf('reference.pdf');self.assertIsNone(self.project()['active'])
  self.s.update({'id':self.a,'changes':{'pin':'notes.pdf'}});(self.s.projects/'Project A/notes.pdf').unlink();self.assertIsNone(self.project()['active']);self.assertEqual(self.project()['pin'],'notes.pdf')
 def test_numeric_versions_unrelated_and_duplicate(self):
  self.pdf('Plan_v1.9.pdf');self.pdf('Plan_v1.10.pdf');self.assertEqual(self.project()['active']['name'],'Plan_v1.10.pdf')
  self.pdf('Other_v99.pdf');self.assertEqual(self.project()['active']['name'],'Plan_v1.10.pdf')
  self.pdf('Plan_v1.10(1).pdf');self.assertIsNone(self.project()['active'])
 def test_preferences_runtime_identity_and_restart(self):
  self.assertEqual(self.s.scan()['server_name'],socket.gethostname());self.s.settings({'kind':'preferences','values':{'theme':'light','server_name':'Studio','card_density':'compact'}})
  new=Store(self.s.data);self.assertEqual(new.scan()['preferences']['theme'],'light');self.assertEqual(new.scan()['server_name'],'Studio');new.settings({'kind':'preferences','values':{'server_name':''}});self.assertEqual(new.scan()['server_name'],socket.gethostname())
 def test_recursive_storage_does_not_follow_links(self):
  sub=self.s.projects/'Project A/nested';sub.mkdir();(sub/'asset.dat').write_bytes(b'123456');baseline=self.s.storage_info()['bytes'];outside=self.root/'secret';outside.write_bytes(b'0'*1000);(sub/'linked').symlink_to(outside);self.assertEqual(self.s.storage_info()['bytes'],baseline)
 def test_reorder_pages_conflict_and_new_discovery(self):
  self.reorder([self.b,self.a],[[self.b],[],[self.a]]);self.assertEqual(Store(self.s.data).scan()['card_pages'],[[self.b],[],[self.a]])
  with self.assertRaises(ValueError):self.reorder(self.ids,revision=0)
  before=copy.deepcopy(self.s.state)
  for order,pages in [([self.a,self.a],None),(self.ids,[[self.a]]),(self.ids,[[self.b,self.a]])]:
   with self.assertRaises(ValueError):self.reorder(order,pages)
  self.assertEqual(before,self.s.state)
  self.s.create_project({'name':'New project'})
  with self.assertRaises(ValueError):self.reorder(self.ids)
 def test_v6_state_and_notes_preserved(self):
  self.s.update({'id':self.a,'changes':{'category':'Creative','priority':'Existing priority','summary':'Keep summary','pin':None}})
  v=self.s.scan()['visual'];self.s.visual_update({'revision':v['revision'],'action':'layout','view':'roadmap','positions':{self.a:{'x':45,'y':75}},'camera':{'x':22,'y':33,'scale':.8}})
  self.s.state.pop('workspace_version');self.s.save();snapshot=copy.deepcopy(self.s.state);(self.s.data/'dashboard.before-v6.5.json').unlink();notes=self.s.data/'ReleaseNotes/v1.0.md';notes.write_text('Existing historical note');atomic_json(self.s.document_path,{'schema':1,'documents':{'example':{'values':{'checkbox':{'value':True}}}}})
  docs=self.s.document_path.read_bytes();new=Store(self.s.data);self.assertEqual(json.loads((new.data/'dashboard.before-v6.5.json').read_text()),snapshot);self.assertEqual(new.scan()['visual'],snapshot['visual']);self.assertEqual(new.document_path.read_bytes(),docs);self.assertEqual(notes.read_text(),'Existing historical note');self.assertEqual(new.state['projects'][self.a]['priority'],'Existing priority')
 def test_backup_restore_preferences_pages(self):
  self.s.settings({'kind':'backup','path':str(self.root/'backups')});self.s.settings({'kind':'preferences','values':{'theme':'light'}});self.reorder(self.ids,[[self.a],[self.b]]);b=self.s.backup('settings');self.reorder(list(reversed(self.ids)));self.s.settings({'kind':'preferences','values':{'theme':'dark'}});self.s.restore(b['name']);s=self.s.scan();self.assertEqual(s['preferences']['theme'],'light');self.assertEqual(s['card_pages'],[[self.a],[self.b]])
if __name__=='__main__':unittest.main()
