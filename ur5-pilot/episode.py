"""Synchronized, physical-unit episode format for the UR5 pilot (no ML dependency)."""

import argparse
import hashlib
import json
from math import atan2, cos, dist, isfinite, sin, sqrt
from pathlib import Path

SCHEMA_VERSION = 'ur5_episode_v1'
ACTION_NAMES = ['dx_m', 'dy_m', 'dz_m', 'drot_x_rad', 'drot_y_rad', 'drot_z_rad', 'fixed_tool_command']


def finite_vector(values, size):
    if len(values) != size or not all(isfinite(x) for x in values):
        raise ValueError(f'Expected {size} finite numbers.')
    return list(values)


def quaternion(values):
    values = finite_vector(values, 4)
    norm = sqrt(sum(x*x for x in values))
    if abs(norm - 1) > 1e-3:
        raise ValueError('Expected a unit wxyz quaternion.')
    return [x/norm for x in values]


def quat_multiply(a, b):
    w, x, y, z = a
    v, i, j, k = b
    return [w*v-x*i-y*j-z*k, w*i+x*v+y*k-z*j, w*j-x*k+y*v+z*i, w*k+x*j-y*i+z*v]


def rotvec_from_quat(values):
    q = quaternion(values)
    if q[0] < 0:
        q = [-x for x in q]
    sine = sqrt(sum(x*x for x in q[1:]))
    scale = 2 if sine < 1e-12 else 2*atan2(sine, q[0])/sine
    return [x*scale for x in q[1:]]


def pose_delta(position, orientation, target_position, target_orientation):
    position, target_position = finite_vector(position, 3), finite_vector(target_position, 3)
    q, target = quaternion(orientation), quaternion(target_orientation)
    relative = quat_multiply(target, [q[0], -q[1], -q[2], -q[3]])
    return [t-p for p, t in zip(position, target_position)] + rotvec_from_quat(relative) + [0.0]


def apply_delta(position, orientation, action):
    action = finite_vector(action, 7)
    if action[6] != 0:
        raise ValueError('This pilot has a fixed tool; gripper command must remain zero.')
    angle = sqrt(sum(x*x for x in action[3:6]))
    scale = 0.5 if angle < 1e-12 else sin(angle/2)/angle
    rotation = [cos(angle/2)] + [x*scale for x in action[3:6]]
    return ([p+d for p, d in zip(finite_vector(position, 3), action[:3])],
            quaternion(quat_multiply(rotation, quaternion(orientation))))


def observation(time_s, rgb, position, orientation, joint_positions, joint_velocities):
    position, orientation = finite_vector(position, 3), quaternion(orientation)
    return {
        'time_s': time_s, 'rgb': rgb,
        'tcp_position_base_m': position, 'tcp_orientation_base_wxyz': orientation,
        'joint_positions_rad': finite_vector(joint_positions, 6),
        'joint_velocities_rad_s': finite_vector(joint_velocities, 6),
        'proprio': position + rotvec_from_quat(orientation) + [0.0, 0.0],
    }


def model_inputs(transition, instruction):
    """Whitelist model inputs: evaluation targets/hidden scene poses never enter here."""
    obs = transition['observation']
    return {'image_path': obs['rgb'], 'proprio': obs['proprio'], 'language_instruction': instruction}


def image_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not (root/path).resolve().is_relative_to(root.resolve()):
        raise ValueError('Image path escapes the episode directory.')
    if not (root/path).is_file():
        raise ValueError(f'Missing episode image: {relative}.')


def validate_transitions(rows, root, control_hz=20):
    if not rows:
        raise ValueError('Empty episode.')
    previous = None
    for index, row in enumerate(rows):
        obs, nxt = row['observation'], row['next_observation']
        if row['step'] != index or abs(obs['time_s'] - index/control_hz) > 1e-6 or abs(nxt['time_s'] - (index+1)/control_hz) > 1e-6:
            raise ValueError(f'Invalid transition timestamp at {index}.')
        for item in (obs, nxt):
            image_path(root, item['rgb'])
            finite_vector(item['proprio'], 8)
            finite_vector(item['joint_positions_rad'], 6)
            finite_vector(item['joint_velocities_rad_s'], 6)
            finite_vector(item['tcp_position_base_m'], 3)
            quaternion(item['tcp_orientation_base_wxyz'])
            expected = item['tcp_position_base_m'] + rotvec_from_quat(item['tcp_orientation_base_wxyz']) + [0.0, 0.0]
            if dist(item['proprio'], expected) > 1e-8:
                raise ValueError(f'Proprioception differs from measured pose at {index}.')
        if previous is not None:
            # Quaternion normalization can differ by a double-precision ULP
            # between macOS/arm64 and Linux/x86_64. Image identity stays exact.
            continuous = obs['rgb'] == previous['rgb'] and abs(obs['time_s'] - previous['time_s']) <= 1e-9
            continuous &= all(dist(obs[key], previous[key]) <= 1e-9 for key in (
                'tcp_position_base_m', 'tcp_orientation_base_wxyz', 'joint_positions_rad', 'joint_velocities_rad_s', 'proprio',
            ))
            if not continuous:
                raise ValueError(f'Observation chain breaks at {index}.')
        target_position, target_quat = apply_delta(obs['tcp_position_base_m'], obs['tcp_orientation_base_wxyz'], row['action'])
        reference = row['evaluation']['target_pose_base_m_wxyz']
        if dist(target_position, reference[:3]) > 1e-6:
            raise ValueError(f'Action translation does not reconstruct the commanded target at {index}.')
        if min(dist(target_quat, reference[3:]), dist(target_quat, [-x for x in reference[3:]])) > 1e-5:
            raise ValueError(f'Action rotation does not reconstruct the commanded target at {index}.')
        if row['is_first'] != (index == 0) or row['is_last'] != (index == len(rows)-1):
            raise ValueError(f'Invalid episode boundary flags at {index}.')
        previous = nxt


def export_run(root):
    root = Path(root)
    config = json.loads((root/'config.json').read_text())
    summary = json.loads((root/'summary.json').read_text())
    samples = [json.loads(line) for line in (root/'steps.jsonl').read_text().splitlines()]
    rows = []
    for index, sample in enumerate(samples):
        if 'observation_before_action' not in sample:
            raise ValueError('This old recording lacks the initial image/pre-action state; do not fabricate it.')
        nxt = observation(sample['time_s'], sample['rgb'], sample['wrist_position_base_m'],
                          sample['wrist_orientation_base_wxyz'], sample['joint_positions_rad'], sample['joint_velocities_rad_s'])
        rows.append({
            'step': index, 'observation': sample['observation_before_action'], 'action': sample['action_delta_base'],
            'next_observation': nxt, 'is_first': index == 0, 'is_last': index == len(samples)-1,
            'evaluation': {
                'target_pose_base_m_wxyz': sample['target_position_base_m'] + sample['target_orientation_base_wxyz'],
                'contact': {'status': 'not_instrumented', 'wrench_validated': False, 'wrench': None},
            },
        })
    validate_transitions(rows, root, config['control_hz'])
    is_hold = config['motion'] != 'x'
    instruction = 'Hold the robot wrist pose.' if is_hold else 'Move the robot wrist along the base X axis.'
    bounded = all(dist(row['action'][:3], [0,0,0]) <= 0.005 and dist(row['action'][3:6], [0,0,0]) <= 0.05 for row in rows)
    metadata = {
        'schema_version': SCHEMA_VERSION, 'task_id': 'ur5_cartesian_motion_pilot',
        'exporter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'language_instruction': instruction, 'control_hz': config['control_hz'],
        'transition_count': len(rows), 'observation_count': len(rows)+1,
        'action_names': ACTION_NAMES, 'action_normalized': False,
        'rotation_convention': 'base-frame rotvec, q_target = q_delta * q_observed, wxyz quaternions',
        'proprio_names': ['tcp_x_m','tcp_y_m','tcp_z_m','tcp_rx_rad','tcp_ry_rad','tcp_rz_rad','fixed_gripper_0','fixed_gripper_1'],
        'joint_names': config.get('joint_names'),
        'native_action_chunk_length': 1,
        'split': 'interface_validation_only',
        'base_pose_world_m_wxyz': samples[0].get('root_pose_world_m_wxyz'),
        'tool': {'kind': 'wrist_link_pilot', 'controlled_link': config['wrist_body'], 'tcp_offset_m_wxyz': [0,0,0,1,0,0,0], 'actuated_gripper': False},
        'camera': {key: summary[key] for key in ('camera_intrinsics','camera_position_world_m','camera_orientation_ros_wxyz')},
        'robot_gravity_disabled': config['robot_gravity_disabled'], 'gravity_compensation': config.get('gravity_compensation', False),
        'quality': {'tracking_passed': summary['passed'], 'within_5mm_0p05rad_action_bounds': bounded},
        'eligible_for_insertion_training': False,
        'exclusion_reason': 'Motion/interface pilot; no peg, hole or insertion success label.',
        'normalization': {'fit_on': 'training insertion episodes only', 'action_normalization_mask': [True]*6+[False], 'statistics_fitted': False},
    }
    (root/'episode.json').write_text(json.dumps(metadata, indent=2, allow_nan=False)+'\n')
    (root/'transitions.jsonl').write_text(''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows))
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    print(json.dumps(export_run(args.run), indent=2))
