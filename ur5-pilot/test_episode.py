"""Regression tests for causal image/action pairing and Cartesian conventions."""

import copy
import json
from math import dist, sqrt
from pathlib import Path
import tempfile
import unittest

from episode import apply_delta, export_run, model_inputs, observation, pose_delta, validate_transitions


class EpisodeTests(unittest.TestCase):
    def make_run(self, root):
        for name in ('initial_rgb.png', 'rgb/0000.png', 'rgb/0001.png'):
            path = root/name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'image-file-stub-for-schema-tests')
        orientation = [1,0,0,0]
        points = [[0,0,0.3], [0.0008,0,0.3], [0.0018,0,0.3]]
        rows = []
        for index in range(2):
            pre = observation(index/20, 'initial_rgb.png' if index == 0 else 'rgb/0000.png',
                              points[index], orientation, [0]*6, [0]*6)
            target = [(index+1)*0.001,0,0.3]
            rows.append({'step':index,'time_s':(index+1)/20,'rgb':f'rgb/{index:04d}.png',
                         'observation_before_action':pre,'action_delta_base':pose_delta(points[index],orientation,target,orientation),
                         'target_position_base_m':target,'target_orientation_base_wxyz':orientation,
                         'wrist_position_base_m':points[index+1],'wrist_orientation_base_wxyz':orientation,
                         'joint_positions_rad':[0]*6,'joint_velocities_rad_s':[0]*6})
        config = {'motion':'x','control_hz':20,'wrist_body':'wrist_3_link','robot_gravity_disabled':False,'gravity_compensation':True}
        summary = {'passed':True,'camera_intrinsics':[[1,0,0],[0,1,0],[0,0,1]],'camera_position_world_m':[0,0,1],'camera_orientation_ros_wxyz':orientation}
        (root/'config.json').write_text(json.dumps(config))
        (root/'summary.json').write_text(json.dumps(summary))
        (root/'steps.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        return rows

    def test_base_frame_rotation_roundtrip_for_noncommuting_rotations(self):
        qx, qy = [sqrt(.5),sqrt(.5),0,0], [sqrt(.5),0,sqrt(.5),0]
        action = pose_delta([0,0,.3],qx,[.003,-.001,.3],qy)
        position, quat = apply_delta([0,0,.3],qx,action)
        self.assertLess(dist(position,[.003,-.001,.3]),1e-12)
        self.assertLess(dist(quat,qy),1e-12)

    def test_image_precedes_action_and_next_image_chains_to_following_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root)
            meta = export_run(root)
            rows = [json.loads(line) for line in (root/'transitions.jsonl').read_text().splitlines()]
            self.assertEqual(rows[0]['observation']['rgb'],'initial_rgb.png')
            self.assertEqual(rows[0]['next_observation'],rows[1]['observation'])
            self.assertAlmostEqual(rows[1]['action'][0],.0012)
            self.assertFalse(meta['eligible_for_insertion_training'])
            self.assertEqual(meta['observation_count'],3)
            self.assertEqual(meta['normalization']['action_normalization_mask'],[True]*6+[False])

    def test_old_post_action_only_log_is_not_fabricated_into_training_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.make_run(root)
            del rows[0]['observation_before_action']
            (root/'steps.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'old recording'):
                export_run(root)

    def test_one_step_image_offset_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root)
            export_run(root)
            rows = [json.loads(line) for line in (root/'transitions.jsonl').read_text().splitlines()]
            rows[1]['observation']['rgb']='rgb/0001.png'
            with self.assertRaisesRegex(ValueError,'chain breaks'):
                validate_transitions(rows,root)

    def test_roundoff_in_cross_platform_quaternion_normalization_is_tolerated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root)
            export_run(root)
            rows = [json.loads(line) for line in (root/'transitions.jsonl').read_text().splitlines()]
            rows[1]['observation']['tcp_orientation_base_wxyz'][0] += 2e-16
            validate_transitions(rows,root)
            rows[1]['observation']['joint_positions_rad'][0] += 1e-4
            with self.assertRaisesRegex(ValueError,'chain breaks'):
                validate_transitions(rows,root)

    def test_target_pose_is_excluded_from_model_inputs(self):
        row = {'observation':{'rgb':'rgb/0000.png','proprio':[0]*8},
               'evaluation':{'target_pose_base_m_wxyz':[9]*7,'hidden_hole_pose':[5]*7}}
        result = model_inputs(row,'Move the wrist.')
        self.assertEqual(set(result),{'image_path','proprio','language_instruction'})

    def test_paths_and_timestamps_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root)
            export_run(root)
            rows = [json.loads(line) for line in (root/'transitions.jsonl').read_text().splitlines()]
            bad = copy.deepcopy(rows)
            bad[0]['observation']['rgb']='../outside.png'
            with self.assertRaisesRegex(ValueError,'escapes'):
                validate_transitions(bad,root)
            rows[0]['next_observation']['time_s']=.1
            with self.assertRaisesRegex(ValueError,'timestamp'):
                validate_transitions(rows,root)


if __name__ == '__main__':
    unittest.main()
