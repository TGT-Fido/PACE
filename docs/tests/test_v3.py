import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'app'))
from server import Store

class V3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = pathlib.Path(self.temp.name)
        self.store = Store(self.data)
        self.folder = self.store.projects / 'Project'
        self.folder.mkdir()
        (self.folder / 'Master_v1.pdf').write_bytes(b'%PDF original bytes')
        self.pid = self.store.scan()['projects'][0]['id']
    def tearDown(self):
        self.temp.cleanup()
    def card(self):
        return self.store.scan()['projects'][0]
    def test_dismissal_persists_and_new_file_raises_warning(self):
        (self.folder / 'Master_v1_TBD.pdf').write_bytes(b'%PDF ambiguous')
        self.assertEqual(self.card()['new_ambiguities'], 1)
        self.store.update({'id': self.pid, 'dismiss_ambiguities': True})
        self.store = Store(self.data)
        self.assertEqual(self.card()['new_ambiguities'], 0)
        self.assertFalse(any('ambiguous' in w for w in self.card()['warnings']))
        (self.folder / 'Master_v2_TBD.pdf').write_bytes(b'%PDF new ambiguity')
        self.assertEqual(self.card()['new_ambiguities'], 1)
    def test_replaced_ambiguous_file_is_new_occurrence(self):
        p = self.folder / 'Master_v1_TBD.pdf'; p.write_bytes(b'first')
        self.store.update({'id': self.pid, 'dismiss_ambiguities': True})
        p.write_bytes(b'a replaced different file')
        self.assertEqual(self.card()['new_ambiguities'], 1)
    def test_forms_preserve_original_and_restore_across_restart(self):
        original = (self.folder / 'Master_v1.pdf').read_bytes()
        info = self.store.document_state(self.pid, 'Master_v1.pdf')
        result = self.store.save_document_state(dict(info, id=self.pid, file='Master_v1.pdf', values={'10R': {'value': False}, '20R': {'value': 'Text'}}))
        self.assertEqual(result['revision'], 1)
        self.store = Store(self.data)
        saved = self.store.document_state(self.pid, 'Master_v1.pdf')
        self.assertEqual(saved['values']['10R']['value'], False)
        self.assertEqual((self.folder / 'Master_v1.pdf').read_bytes(), original)
    def test_concurrent_save_conflict_and_changed_original(self):
        info = self.store.document_state(self.pid, 'Master_v1.pdf')
        body = dict(info, id=self.pid, file='Master_v1.pdf', values={'1': {'value': True}})
        self.assertEqual(self.store.save_document_state(body)['revision'], 1)
        self.assertIsNone(self.store.save_document_state(body))
        (self.folder / 'Master_v1.pdf').write_bytes(b'%PDF replaced content')
        self.assertIsNone(self.store.save_document_state(body))
        self.assertEqual(self.store.document_state(self.pid, 'Master_v1.pdf')['values'], {})
    def test_state_is_separate_per_version_and_follows_folder_rename(self):
        info = self.store.document_state(self.pid, 'Master_v1.pdf')
        self.store.save_document_state(dict(info, id=self.pid, file='Master_v1.pdf', values={'1': {'value': True}}))
        (self.folder / 'Master_v2.pdf').write_bytes(b'%PDF new version')
        self.assertEqual(self.store.document_state(self.pid, 'Master_v2.pdf')['values'], {})
        self.folder.rename(self.folder.with_name('Renamed'))
        self.assertTrue(self.store.document_state(self.pid, 'Master_v1.pdf')['values']['1']['value'])
    def test_invalid_form_data_and_path_traversal_rejected(self):
        info = self.store.document_state(self.pid, 'Master_v1.pdf')
        for values in [{'x': {'script': 'alert(1)'}}, {'x': {'value': {'nested': 'bad'}}}, {'x': {'value': [4]}}]:
            with self.assertRaises(ValueError):
                self.store.save_document_state(dict(info, id=self.pid, file='Master_v1.pdf', values=values))
        for name in ['../config.json', '..\\config.json', '\x00.pdf']:
            with self.assertRaises(ValueError): self.store.document_state(self.pid, name)
    def test_invalid_document_state_is_never_reset(self):
        (self.data / 'document_state.json').write_text('{bad')
        with self.assertRaises(ValueError): Store(self.data)
        self.assertEqual((self.data / 'document_state.json').read_text(), '{bad')

if __name__ == '__main__': unittest.main(verbosity=2)
