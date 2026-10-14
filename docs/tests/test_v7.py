import base64,copy,json,pathlib,socket,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'app'))
from server import Store,Server,atomic_json
from network import Listeners
from bootstrap import prepare_data
class V7Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=pathlib.Path(self.tmp.name)/'data';self.s=Store(self.data)
 def tearDown(self):self.tmp.cleanup()
 def test_image_duplicate_and_collision(self):
  raw=b'\x89PNG\r\n\x1a\nTEST';body={'kind':'background','action':'upload','name':'Test.png','data':base64.b64encode(raw).decode()}
  self.s.settings(body);first=self.s.state['background'];self.s.settings(dict(body,name='Another.png'));self.assertEqual(first,self.s.state['background']);self.assertEqual(len(self.s.images('background')),1)
  self.s.settings(dict(body,data=base64.b64encode(raw+b'2').decode()));self.assertNotEqual(first,self.s.state['background'])
 def test_migration_preserves_wallpaper(self):
  old=self.data/'assets';old.mkdir();(old/'old.png').write_bytes(b'png');self.s.state['background']='/background/old.png';self.s.save();new=Store(self.data);self.assertEqual((self.data/'backgrounds/old.png').read_bytes(),b'png');self.assertEqual(new.state['background'],'/background/old.png');self.assertFalse(old.exists())
 def test_restore_old_wallpaper_migrates_immediately(self):
  old=self.data/'assets';old.mkdir();(old/'restored.png').write_bytes(b'old wallpaper');self.s.state['background']='/background/restored.png';self.s.save()
  backup=self.s.backup('full');self.s.settings({'kind':'background','action':'reset'});self.s.restore(backup['name'])
  self.assertEqual((self.data/'backgrounds/restored.png').read_bytes(),b'old wallpaper');self.assertEqual(self.s.state['background'],'/background/restored.png');self.assertFalse(old.exists())
 def test_preset_and_title_persist(self):
  self.s.settings({'kind':'preferences','values':{'theme':'light'}});self.s.settings({'kind':'custom-theme','action':'save'});self.s.settings({'kind':'preferences','values':{'theme':'dark'}});self.s.settings({'kind':'custom-theme','action':'apply'});self.s.settings({'kind':'v7','values':{'map_title':'My roadmap','rendering':'hdr'}});new=Store(self.data);self.assertEqual(new.state['preferences']['theme'],'light');self.assertEqual(new.state['preferences']['map_title'],'My roadmap')
 def test_delete_project_removes_only_selected(self):
  a=self.s.create_project({'name':'Delete me'});b=self.s.create_project({'name':'Keep me'});folder=self.s.projects/a['folder'];(folder/'sample.pdf').write_bytes(b'%PDF')
  with self.assertRaises(ValueError):self.s.delete_project({'id':a['id'],'confirm_name':'wrong'})
  self.assertTrue(folder.exists());self.s.state['visual']['parents'][b['id']]=a['id'];self.s.state['card_pages']=[[a['id'],b['id']]]
  self.s.delete_project({'id':a['id'],'confirm_name':a['name']});self.assertFalse(folder.exists());self.assertEqual([x['id'] for x in Store(self.data).scan()['projects']],[b['id']]);self.assertNotIn(b['id'],self.s.state['visual']['parents']);self.assertEqual(self.s.state['card_pages'],[[b['id']]])
 def test_delete_link_rejected(self):
  a=self.s.create_project({'name':'Linked'});outside=self.data/'outside';outside.write_text('keep');(self.s.projects/a['folder']/'link').symlink_to(outside)
  with self.assertRaises(ValueError):self.s.delete_project({'id':a['id'],'confirm_name':a['name']})
  self.assertEqual(outside.read_text(),'keep')
 def test_connections_fail_without_changing_active_mode(self):
  self.s.config['port']=0;manager=Listeners(self.s,Server)
  try:
   manager.switch('local');self.assertEqual(list(manager.servers),['127.0.0.1'])
   with patch('network.tailscale_addresses',side_effect=ValueError('offline')):
    with self.assertRaises(ValueError):manager.switch('tailscale')
   self.assertEqual(manager.mode,'local');self.assertEqual(list(manager.servers),['127.0.0.1'])
   with patch('network.lan_addresses',return_value=['127.0.0.2']):manager.switch('lan')
   self.assertEqual(len(manager.servers),2);manager.switch('local');self.assertEqual(list(manager.servers),['127.0.0.1'])
  finally:manager.close()
 def test_bootstrap_does_not_replace_existing_data(self):
  a=self.s.create_project({'name':'My existing project'});prepare_data(self.data);self.assertEqual([x['id'] for x in Store(self.data).scan()['projects']],[a['id']])
 def test_fresh_install_is_seeded_once(self):
  new=pathlib.Path(self.tmp.name)/'fresh';prepare_data(new);s=Store(new);self.assertEqual(len(s.scan()['projects']),4)
  for p in list(s.scan()['projects']):s.delete_project({'id':p['id'],'confirm_name':p['name']})
  prepare_data(new);self.assertEqual(Store(new).scan()['projects'],[])
if __name__=='__main__':unittest.main()
