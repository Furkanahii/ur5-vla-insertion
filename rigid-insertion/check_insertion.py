"""Recompute acceptance from measured tool poses and verify saved episode files."""

import json
from pathlib import Path
import struct
import sys
from math import dist

from episode import pose_delta,validate_transitions
from dataset_manifest import CONTRACT,verify_run_case
from task_math import TaskSpec,insertion_metrics


def check(run):
    run=Path(run)
    config=json.loads((run/'config.json').read_text())
    summary=json.loads((run/'summary.json').read_text())
    rows=[json.loads(line) for line in (run/'steps.jsonl').read_text().splitlines()]
    transitions=[json.loads(line) for line in (run/'transitions.jsonl').read_text().splitlines()]
    metadata=json.loads((run/'episode.json').read_text())
    if len(rows)!=150 or len(transitions)!=150 or summary['frame_count']!=150 or metadata['observation_count']!=151:
        raise ValueError('Expected 150 actions and 151 observations.')
    validate_transitions(transitions,run,config['control_hz'])
    if config.get('tcp_frame')=='tip_z_up_v1':
        orientations=[row['observation']['proprio'][3:6] for row in transitions]
        if max(dist(a,b) for a,b in zip(orientations,orientations[1:]))>.1:
            raise ValueError('Discontinuous proprioception orientation in the new TCP frame.')
    for relative in ['initial_rgb.png']+[f'rgb/{i:04d}.png' for i in range(150)]:
        with (run/relative).open('rb') as stream: header=stream.read(24)
        if header[:8]!=b'\x89PNG\r\n\x1a\n' or len(header)!=24 or struct.unpack('>II',header[16:24])!=(640,480):
            raise ValueError(f'Invalid image: {relative}')
    spec=TaskSpec()
    streak=longest=0
    depths=[]
    peak_contact=0
    for row in rows:
        evidence=row['evaluation']
        measured=insertion_metrics(evidence['tool_tip_world_m'],evidence['tool_orientation_world_wxyz'],
                                   config['geometry']['hole_top_world_m'],spec)
        if abs(measured['depth_m']-evidence['insertion']['depth_m'])>1e-8:
            raise ValueError('Reported depth differs from measured tool pose.')
        streak=streak+1 if measured['instant_success'] else 0
        longest=max(longest,streak)
        depths.append(measured['depth_m'])
        peak_contact=max(peak_contact,evidence['contact']['peak_normal_force_n_raw'])
    success=streak>=spec.success_hold_steps
    if success!=summary['task_success']:
        raise ValueError('Task success does not match measured pose history.')
    passed=success if config['scenario']=='aligned' else not success and max(depths)<.002 and peak_contact>.5
    if not passed or not summary['validation_passed']:
        raise ValueError(f'Physical scenario acceptance failed: {config["scenario"]}')
    if metadata.get('scenario_id'):
        case=verify_run_case(run,config,metadata)
        if not success or not metadata.get('eligible_for_insertion_dataset'):
            raise ValueError('Failed episode cannot enter the successful expert dataset.')
        if metadata['eligible_for_insertion_training']!=(case['split']=='train'):
            raise ValueError('Only training split episodes may be used for fitting.')
        initial=transitions[0]['observation']
        error=pose_delta(initial['tcp_position_base_m'],initial['tcp_orientation_base_wxyz'],
                         initial['tcp_position_base_m'],config['requested_initial_tcp_quaternion_wxyz'])
        if dist(error[3:6],[0,0,0])>.15*3.141592653589793/180:
            raise ValueError('Recorded initial orientation does not match physical tilt request.')
        if dist(config['camera_position_world_m'],CONTRACT['camera_position_world_m'])>1e-6:
            raise ValueError('Dataset camera must be fixed across fixture offsets.')
    elif metadata['eligible_for_insertion_training'] or metadata.get('eligible_for_insertion_dataset'):
        raise ValueError('Physics controls cannot enter the training dataset.')
    if metadata['contact_wrench_validated']:
        raise ValueError('Raw normal forces are not a validated contact wrench.')
    print(f'INSERTION_VERIFIED: {config["scenario"]}, task_success={success}, max_depth={max(depths):.6f} m')


if __name__=='__main__':
    check(sys.argv[1])
