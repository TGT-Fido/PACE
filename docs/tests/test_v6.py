import pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'app'))
from server import Store
class V6Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.tmp.name);self.s=Store(self.base/'install/data');self.a=self.s.create_project({'name':'A'})['id'];self.b=self.s.create_project({'name':'B'})['id'];self.c=self.s.create_project({'name':'C'})['id']
 def tearDown(self):self.tmp.cleanup()
 def put(self,**body):return self.s.visual_update({'revision':self.s.scan()['visual']['revision'],**body})
 def test_independent_layouts_restart_and_startup(self):
  self.put(action='layout',view='canvas',positions={self.a:{'x':300,'y':80}},collapsed=[self.a],camera={'x':100,'y':20,'scale':.6})
  self.put(action='layout',view='roadmap',positions={self.a:{'x':-30,'y':-70}})
  self.put(action='startup',view='radial');v=Store(self.s.data).scan()['visual']
  self.assertEqual(v['startup'],'radial');self.assertEqual(v['layouts']['canvas']['positions'][self.a]['x'],300);self.assertEqual(v['layouts']['roadmap']['positions'][self.a]['x'],-30);self.assertEqual(v['layouts']['radial']['positions'],{})
  self.put(action='reset',view='canvas');self.assertEqual(self.s.scan()['visual']['layouts']['roadmap']['positions'][self.a]['x'],-30)
 def test_parent_cycles_and_revert(self):
  self.put(action='parent',child=self.b,parent=self.a);self.put(action='parent',child=self.c,parent=self.b)
  with self.assertRaisesRegex(ValueError,'circular'):self.put(action='parent',child=self.a,parent=self.c)
  with self.assertRaises(ValueError):self.put(action='parent',child=self.a,parent=self.a)
  self.put(action='parent',child=self.b,parent=None);self.assertNotIn(self.b,self.s.scan()['visual']['parents'])
 def test_related_link_remove_and_layout_reset_preserves(self):
  v=self.put(action='link',**{'from':self.a,'to':self.b,'label':'Depends on','directed':True});edge=v['links'][0]
  self.put(action='reset',view='roadmap');self.assertEqual(self.s.scan()['visual']['links'][0],edge)
  self.put(action='unlink',id=edge['id']);self.assertEqual(self.s.scan()['visual']['links'],[])
 def test_stale_revision_cannot_overwrite(self):
  rev=self.s.scan()['visual']['revision'];self.put(action='startup',view='roadmap')
  with self.assertRaisesRegex(ValueError,'another device'):self.s.visual_update({'revision':rev,'action':'startup','view':'cards'})
  self.assertEqual(self.s.scan()['visual']['startup'],'roadmap')
 def test_invalid_layout_rejected_without_changes(self):
  v=self.s.scan()['visual']
  for value in [float('nan'),float('inf'),100001,True,'4']:
   with self.assertRaises(ValueError):self.put(action='layout',view='canvas',positions={self.a:{'x':value,'y':0}})
  for camera in [{'x':0,'y':0,'scale':0},{'x':0,'y':0,'scale':5},{'x':0}]:
   with self.assertRaises(ValueError):self.put(action='layout',view='canvas',camera=camera)
  self.assertEqual(v,self.s.scan()['visual'])
 def test_category_rename_and_delete_preserves_links(self):
  self.s.settings({'kind':'category','action':'add','name':'Testing'});self.put(action='parent',child=self.a,parent='group:Testing');self.put(action='layout',view='canvas',positions={'group:Testing':{'x':1,'y':2}},focus='group:Testing');self.put(action='link',**{'from':'group:Testing','to':self.b})
  self.s.settings({'kind':'category','action':'rename','name':'Testing','new_name':'Renamed'});v=self.s.scan()['visual'];self.assertEqual(v['parents'][self.a],'group:Renamed');self.assertIn('group:Renamed',v['layouts']['canvas']['positions']);self.assertEqual(v['links'][0]['from'],'group:Renamed')
  self.s.settings({'kind':'category','action':'delete','name':'Renamed'});self.assertEqual(self.s.scan()['visual']['parents'][self.a],'group:Other')
 def test_backup_restore_visuals_and_revision(self):
  self.s.settings({'kind':'backup','path':str(self.base/'backups')});self.put(action='startup',view='radial');self.put(action='parent',child=self.a,parent=self.b);b=self.s.backup('settings')
  self.put(action='startup',view='roadmap');self.put(action='parent',child=self.a,parent=None);old=self.s.scan()['visual']['revision'];self.s.restore(b['name']);v=self.s.scan()['visual'];self.assertEqual(v['startup'],'radial');self.assertEqual(v['parents'][self.a],self.b);self.assertGreater(v['revision'],old)
 def test_migrate_old_data_and_never_move_folders(self):
  self.put(action='parent',child=self.a,parent=self.b);self.put(action='layout',view='canvas',positions={self.a:{'x':80,'y':60}});self.assertTrue((self.s.projects/'A').is_dir());self.assertTrue((self.s.projects/'B').is_dir())
  self.s.state.pop('visual');self.s.save();s=Store(self.s.data);self.assertEqual(s.scan()['visual']['startup'],'cards');self.assertEqual(len(s.scan()['projects']),3)
if __name__=='__main__':unittest.main()
