"""Frozen pilot cases; assignment and geometry are verified before use.

This small dataset exercises the conversion pipeline. It is not a statistically
representative benchmark, and the held-out cases must not be used for fitting.
"""
import hashlib
import json
from pathlib import Path

from task_math import TaskSpec, hole_top_position, tilt_quaternion

CONTRACT={
    'task_id':'ur5_rigid_peg_insertion_v2',
    'spec':TaskSpec().metadata(),
    'tcp_frame':'tip_z_up_v1',
    'camera_position_world_m':[.82,.40,.43],
    'camera_look_at_world_m':[ *hole_top_position()[:2], hole_top_position()[2]+.025 ],
    'camera_resolution':[640,480],
    'camera_focal_length_mm':30.0,
    'expert':'align_position_and_orientation_30_insert_100_dwell_20',
    'setup':'rotate_at_fixed_tip_30_hold_10',
    'joint_stiffness':800.0,'joint_damping':60.0,
    'gravity_compensation':True,
    'instruction':'Insert the peg into the hole.',
    'tilt_convention':'base-frame rotation vector x/y in degrees; not Euler angles',
}
PARAMETERS=('offset_x_mm','offset_y_mm','tilt_x_deg','tilt_y_deg')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def case_id(parameters,contract=CONTRACT):
    return 'case-'+digest({'contract':contract,'parameters':parameters})[:16]


def load_manifest(path):
    manifest=json.loads(Path(path).read_text())
    if manifest.get('schema_version')!='ur5_insertion_manifest_v1' or manifest.get('contract')!=CONTRACT:
        raise ValueError('Unknown manifest schema or task contract.')
    seen=set()
    splits=set()
    for case in manifest['cases']:
        if case['split'] not in ('train','validation','test'):
            raise ValueError('Unknown split.')
        p=case['parameters']
        if set(p)!=set(PARAMETERS): raise ValueError('Unexpected case parameters.')
        hole_top_position((p['offset_x_mm']/1000,p['offset_y_mm']/1000))
        tilt_quaternion(p['tilt_x_deg'],p['tilt_y_deg'])
        expected=case_id(p,manifest['contract'])
        if case['id']!=expected or expected in seen:
            raise ValueError('Case ID mismatch or duplicate scenario across splits.')
        seen.add(expected)
        splits.add(case['split'])
    if not manifest['cases'] or splits!={'train','validation','test'}:
        raise ValueError('Expected nonempty, distinct train/validation/test cases.')
    return manifest,digest(manifest)


def get_case(manifest,identifier):
    matches=[case for case in manifest['cases'] if case['id']==identifier]
    if len(matches)!=1: raise ValueError('Scenario ID must identify exactly one case.')
    return matches[0]


def verify_run_case(run,config,metadata):
    manifest,sha=load_manifest(Path(run)/'dataset_manifest.json')
    case=get_case(manifest,metadata['scenario_id'])
    if metadata['manifest_sha256']!=sha or metadata['split']!=case['split']:
        raise ValueError('Episode split or manifest hash mismatch.')
    if config['dataset_case']!=case or config['manifest_sha256']!=sha:
        raise ValueError('Run configuration does not match manifest.')
    if config['task_id']!=CONTRACT['task_id'] or config['scenario']!='aligned':
        raise ValueError('Only aligned v2 episodes belong to this dataset.')
    p=case['parameters']
    if config['geometry']['fixture_offset_xy_m']!=[p['offset_x_mm']/1000,p['offset_y_mm']/1000]:
        raise ValueError('Actual fixture offset differs from manifest.')
    if config['requested_initial_tcp_quaternion_wxyz']!=tilt_quaternion(p['tilt_x_deg'],p['tilt_y_deg']):
        raise ValueError('Requested physical tilt differs from manifest.')
    return case
