import copy
import json
from pathlib import Path
import tempfile
import unittest

from dataset_manifest import load_manifest


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.path=Path(__file__).with_name('pilot_manifest.json')

    def modified(self,manifest):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'manifest.json'
            path.write_text(json.dumps(manifest))
            return load_manifest(path)

    def test_cases_are_distinct_and_have_frozen_assignments(self):
        m,sha=load_manifest(self.path)
        self.assertEqual([sum(c['split']==s for c in m['cases']) for s in ('train','validation','test')],[8,2,2])
        self.assertEqual(len({c['id'] for c in m['cases']}),12)
        changed=copy.deepcopy(m)
        changed['cases'][0]['split']='test'
        self.assertNotEqual(self.modified(changed)[1],sha)

    def test_duplicate_config_across_splits_is_rejected(self):
        m,_=load_manifest(self.path)
        duplicate=copy.deepcopy(m['cases'][0])
        duplicate['split']='test'
        m['cases'].append(duplicate)
        with self.assertRaisesRegex(ValueError,'duplicate'): self.modified(m)

    def test_mutated_parameter_without_new_id_is_rejected(self):
        m,_=load_manifest(self.path)
        m['cases'][0]['parameters']['tilt_x_deg']=1.25
        with self.assertRaisesRegex(ValueError,'ID mismatch'): self.modified(m)


if __name__=='__main__': unittest.main()
