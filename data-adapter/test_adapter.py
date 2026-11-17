import copy
import unittest
import numpy as np

from adapter_core import fit_statistics,normalize


def episode(split,identifier,value):
    return {'split':split,'id':identifier,'transitions':[{'action':[value]*6+[0.0],
             'observation':{'proprio':[value]*6+[0.0,0.0]}}]}


class NormalizationTests(unittest.TestCase):
    def test_held_out_changes_do_not_change_training_statistics(self):
        episodes=[episode('train','a',.001),episode('train','b',.002),episode('validation','c',10),episode('test','d',-10)]
        before=fit_statistics(episodes,'frozen-manifest')
        changed=copy.deepcopy(episodes)
        changed[2]=episode('validation','c',1e9)
        changed[3]=episode('test','d',-1e9)
        self.assertEqual(before,fit_statistics(changed,'frozen-manifest'))
        self.assertEqual(before['provenance']['scenario_ids'],['a','b'])

    def test_noise_floor_and_constant_tool_dimensions(self):
        stats=fit_statistics([episode('train','a',1e-8),episode('train','b',2e-8)],'manifest')
        result=normalize([[1.5e-8]*6+[0]],stats['action'])
        self.assertTrue(np.all(np.abs(result)<1e-3))
        self.assertEqual(result[0,-1],0)
        self.assertTrue(np.isfinite(result).all())
        self.assertGreaterEqual(stats['action']['q99'][0]-stats['action']['q01'][0],1e-4-1e-12)

    def test_no_implicit_fallback_to_eval_data(self):
        with self.assertRaisesRegex(ValueError,'No training'):
            fit_statistics([episode('test','held-out',0)],'manifest')


if __name__=='__main__': unittest.main()
