import base64,hashlib,io,json,pathlib,shutil,sys,tempfile,threading,time,unittest,zipfile
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]/'app'))
from server import Store,Server
from features import read_archive,PRESETS
from pypdf import PdfWriter

class V5Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.temp.name);self.s=Store(self.base/'install/data');self.s.settings({'kind':'backup','path':str(self.base/'backups')});self.p=self.s.create_project({'name':'Testing'})
 def tearDown(self):
  for _ in range(200):
   if not self.s.index_status['running']:break
   time.sleep(.01)
  self.temp.cleanup()
 def raw(self):
  w=PdfWriter();w.add_blank_page(width=200,height=200);b=io.BytesIO();w.write(b);return b.getvalue()
 def upload(self,name='Master_v1.pdf',raw=None):
  return self.s.upload({'id':self.p['id'],'name':name,'data':base64.b64encode(raw or self.raw()).decode(),'note':'First draft'})
 def wait(self):
  for _ in range(300):
   if not self.s.index_status['running']:return
   time.sleep(.01)
  self.fail('Index did not complete')
 def test_create_upload_duplicate_pin_and_restart(self):
  self.upload();self.wait();pid=self.p['id'];self.s.update({'id':pid,'changes':{'pin':'Master_v1.pdf','badges':['Audio'],'color':'#3232fa'}});self.upload('Master_v2.pdf');self.wait()
  with self.assertRaises(ValueError):self.upload()
  s=Store(self.s.data);p=s.scan()['projects'][0];self.assertEqual(p['active']['name'],'Master_v1.pdf');self.assertEqual(p['files'][0]['note'],'First draft');self.assertEqual(len(p['files']),2)
 def test_invalid_names_and_invalid_pdf(self):
  for name in ['../Bad','CON','a/b','a\\b','Bad.',' Bad']:
   with self.assertRaises(ValueError):self.s.create_project({'name':name})
  with self.assertRaises(ValueError):self.upload(raw=b'%PDF-corrupt')
  with self.assertRaises(ValueError):self.s.create_project({'name':'testing'})
 def test_full_backup_restores_data_and_removes_later_project(self):
  self.upload();self.wait();self.s.update({'id':self.p['id'],'changes':{'summary':'Saved summary'}})
  backup=self.s.backup();(self.s.projects/'Testing/Master_v1.pdf').unlink();self.s.create_project({'name':'Later'})
  self.s.restore(backup['name']);cards=self.s.scan()['projects'];self.assertEqual(len(cards),1);self.assertEqual(cards[0]['summary'],'Saved summary');self.assertEqual((self.s.projects/'Testing/Master_v1.pdf').read_bytes(),self.raw())
  self.assertEqual(len(self.s.backup_info()['backups']),2)
 def test_settings_only_omits_pdfs_and_preserves_live_files(self):
  self.upload();self.wait();b=self.s.backup('settings')
  with zipfile.ZipFile(b['path']) as z:self.assertFalse(any(n.endswith('.pdf') for n in z.namelist()));self.assertIn('data/Projects/Testing/.pace-id.json',z.namelist())
  self.upload('Master_v2.pdf');self.wait();self.s.restore(b['name']);self.assertTrue((self.s.projects/'Testing/Master_v2.pdf').exists())
 def test_backup_rejects_live_destination_and_tampered_backup(self):
  for p in [self.s.data,self.s.data/'backup',self.s.data.parent]:
   with self.assertRaises(ValueError):self.s.settings({'kind':'backup','path':str(p)})
  b=self.s.backup()
  with zipfile.ZipFile(b['path'],'a') as z:z.writestr('../escape','bad')
  with self.assertRaises(ValueError):self.s.restore(b['name'])
 def test_backup_refuses_symlink(self):
  (self.s.data/'link').symlink_to(self.base/'backups',target_is_directory=True)
  with self.assertRaises(ValueError):self.s.backup()
 def test_color_names_brightness_and_release_notes(self):
  self.assertGreaterEqual(len(PRESETS),20);self.s.settings({'kind':'color','value':'#123456','name':'Ocean'});self.s.settings({'kind':'brightness','value':90});s=Store(self.s.data)
  self.assertEqual(s.scan()['colors']['#123456'],'Ocean');self.assertEqual(s.scan()['brightness'],90);self.assertTrue(s.release_notes())
  with self.assertRaises(ValueError):s.settings({'kind':'color','value':'#112233','name':'Ocean'})
 def test_overview_and_content_search(self):
  # A small valid PDF with a standard font and a searchable page stream.
  from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
  w=PdfWriter();page=w.add_blank_page(width=300,height=300)
  font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
  page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):w._add_object(font)})})
  stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 200 Td (quasar monitoring unique) Tj ET');page[NameObject('/Contents')]=w._add_object(stream);b=io.BytesIO();w.write(b)
  self.upload(raw=b.getvalue());self.wait();self.assertIn(self.p['id'],self.s.search('Testing','overview')['ids']);self.assertEqual(self.s.search('quasar','overview')['ids'],[])
  r=self.s.search('quasar','contents');self.assertEqual(r['hits'][0]['page'],1);self.assertIn('quasar',r['hits'][0]['excerpt'])
  (self.s.projects/'Testing/Master_v1.pdf').unlink();self.assertEqual(self.s.search('quasar','contents')['hits'],[])
 def test_image_pdf_index_explains_limit(self):
  self.upload();self.wait();self.assertIn('OCR',self.s.index_status['errors'][0]['message'])
 def test_update_unconfigured_and_bad_checksum(self):
  self.assertFalse(self.s.check_update()['configured'])
  self.s.staged={'version':'99.0.0','url':'https://example.invalid/app.zip','sha256':'0'*64}
  with patch('features.https_bytes',return_value=b'bad'):
   with self.assertRaises(ValueError):self.s.prepare_update()
 def test_update_stage_checks_version_and_makes_backup(self):
  m={'format':'PACE-update-1','version':'99.0.0','url':'https://example.invalid/app.zip','sha256':''}
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:z.writestr('app/server.py','print("candidate")');z.writestr('app/VERSION','99.0.0')
  raw=b.getvalue();m['sha256']=hashlib.sha256(raw).hexdigest();self.s.state['update_url']='https://example.invalid/latest.json'
  with patch('features.https_bytes',return_value=json.dumps(m).encode()):self.assertTrue(self.s.check_update()['available'])
  with patch('features.https_bytes',return_value=raw):job=self.s.prepare_update()
  self.assertTrue(pathlib.Path(job['backup']).exists());self.assertTrue((pathlib.Path(job['work'])/'new/app/server.py').exists())
 def test_offline_full_restore(self):
  import importlib.util
  path=pathlib.Path(__file__).resolve().parents[2]/'RECOVER_PACE.py';spec=importlib.util.spec_from_file_location('recover',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  self.upload();self.wait();b=self.s.backup();target=self.base/'recovery-test';target.mkdir();(target/'data').mkdir();(target/'data/config.json').write_text('broken json');previous=mod.recover(b['path'],target)
  self.assertTrue((target/'app/server.py').exists());self.assertTrue((target/'data/Projects/Testing/Master_v1.pdf').exists());self.assertTrue(pathlib.Path(previous).exists())
if __name__=='__main__':unittest.main()

class WorkerTests(unittest.TestCase):
 def test_worker_success_and_rollback(self):
  import update_worker
  from unittest.mock import MagicMock
  for success in [True,False]:
   with self.subTest(success=success),tempfile.TemporaryDirectory() as td:
    base=pathlib.Path(td);app=base/'app';app.mkdir();(app/'marker').write_text('old');data=base/'data';data.mkdir();(data/'value').write_text('original');work=base/'work';(work/'new/app').mkdir(parents=True);(work/'new/app/marker').write_text('new')
    proc=MagicMock();proc.poll.return_value=None if success else 1
    response=MagicMock();response.__enter__.return_value=io.BytesIO(b'{"app":"PACE","version":"99.0.0"}')
    with patch('update_worker.subprocess.Popen',return_value=proc) as pop,patch('update_worker.time.sleep'),patch('update_worker.urllib.request.urlopen',return_value=response):
     if success:update_worker.apply(work,app,data,['mock'],'http://localhost','99.0.0')
     else:
      with self.assertRaises(RuntimeError):update_worker.apply(work,app,data,['mock'],'http://localhost','99.0.0')
     self.assertEqual((app/'marker').read_text(),'new' if success else 'old');self.assertEqual((data/'value').read_text(),'original');self.assertEqual(pop.call_count,1 if success else 2)
