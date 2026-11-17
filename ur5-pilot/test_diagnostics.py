"""CPU regressions for measurements and recorded pose replay, without Isaac Lab."""

import json
from pathlib import Path
import tempfile
import unittest

from diagnostics import analyze, orientation_error_deg, tracking_metrics
from motion import orientations, targets


class DiagnosticsTests(unittest.TestCase):
    def test_transient_z_sag_is_detected_even_with_perfect_endpoint(self):
        records = [
            {'target_position_base_m': [0.01, 0, 0.5], 'wrist_position_base_m': [0, 0, 0.47]},
            {'target_position_base_m': [0.03, 0, 0.5], 'wrist_position_base_m': [0.03, 0, 0.5]},
        ]
        metrics = tracking_metrics(records, [0, 0, 0.5])
        self.assertAlmostEqual(metrics['max_abs_tracking_error_xyz_m'][2], 0.03)
        self.assertEqual(metrics['final_tracking_error_xyz_m'], [0, 0, 0])
        self.assertAlmostEqual(metrics['z_displacement_range_m'][0], -0.03)

    def test_intended_z_motion_is_not_reported_as_tracking_error(self):
        records = [{'target_position_base_m': [0, 0, 0.4], 'wrist_position_base_m': [0, 0, 0.4]}]
        metrics = tracking_metrics(records, [0, 0, 0.5])
        self.assertEqual(metrics['max_abs_tracking_error_xyz_m'][2], 0)
        self.assertAlmostEqual(metrics['final_displacement_xyz_m'][2], -0.1)

    def test_quaternion_sign_does_not_change_orientation(self):
        self.assertEqual(orientation_error_deg([1, 0, 0, 0], [-1, 0, 0, 0]), 0)
        self.assertAlmostEqual(orientation_error_deg([1, 0, 0, 0], [0, 1, 0, 0]), 180)

    def test_nonfinite_and_empty_logs_are_rejected(self):
        with self.assertRaises(ValueError):
            tracking_metrics([], [0, 0, 0])
        with self.assertRaises(ValueError):
            tracking_metrics([{'target_position_base_m': [0, 0, 0], 'wrist_position_base_m': [0, 0, float('nan')]}], [0, 0, 0])

    def test_replay_preserves_recorded_orientation_and_validates_timestamps(self):
        initial = [0, 0, 0.5]
        recorded_targets = targets(initial, 0.03)
        recorded_quaternion = [0, 1, 0, 0]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'steps.jsonl'
            rows = [dict(step=i, time_s=(i + 1) / 20, target_position_base_m=p,
                         target_orientation_base_wxyz=recorded_quaternion) for i, p in enumerate(recorded_targets)]
            source.write_text('\n'.join(json.dumps(row) for row in rows))
            self.assertEqual(targets(initial, 0.03, source), recorded_targets)
            self.assertEqual(orientations([1, 0, 0, 0], source)[0], recorded_quaternion)
            rows[4]['time_s'] = 0
            source.write_text('\n'.join(json.dumps(row) for row in rows))
            with self.assertRaises(ValueError):
                targets(initial, 0.03, source)
            rows[4]['target_orientation_base_wxyz'] = [0, 0, 0, 0]
            source.write_text('\n'.join(json.dumps(row) for row in rows))
            with self.assertRaises(ValueError):
                orientations([1, 0, 0, 0], source)

    def test_old_log_marks_unknown_initial_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'steps.jsonl'
            source.write_text(json.dumps({'target_position_base_m': [0, 0, 0.5], 'wrist_position_base_m': [0, 0, 0.49]}) + '\n')
            report = analyze(source)
            self.assertIn('unavailable', report['initial_reference'])
            self.assertIsNone(report['config'])

    def test_hold_is_constant_and_does_not_alias_initial(self):
        initial = [0, 0, 0.5]
        positions = targets(initial, 0, hold=True)
        self.assertEqual(len(positions), 50)
        self.assertTrue(all(p == initial for p in positions))
        positions[0][2] = 0
        self.assertEqual(positions[1], initial)


if __name__ == '__main__':
    unittest.main()
