"""Check saved pilot artifacts, even when the simulator replaces its exit status."""

import json
from pathlib import Path
import struct
import sys

from diagnostics import tracking_metrics
from episode import SCHEMA_VERSION, validate_transitions


def check(run: Path) -> None:
    summary = json.loads((run / 'summary.json').read_text())
    rows = [json.loads(line) for line in (run / 'steps.jsonl').read_text().splitlines()]
    if summary['frame_count'] != 50 or len(rows) != 50:
        raise ValueError('Expected 50 samples and frames.')
    for index, row in enumerate(rows):
        if row['step'] != index or abs(row['time_s'] - (index + 1) / 20) > 1e-6:
            raise ValueError(f'Invalid timestamp or index at sample {index}.')
        expected = f'rgb/{index:04d}.png'
        if row['rgb'] != expected:
            raise ValueError(f'Unexpected RGB path at sample {index}.')
        with (run / expected).open('rb') as stream:
            header = stream.read(24)
        if header[:8] != b'\x89PNG\r\n\x1a\n' or len(header) != 24 or struct.unpack('>II', header[16:24]) != (320, 240):
            raise ValueError(f'Invalid PNG header: {expected}.')
    metrics = tracking_metrics(rows, summary['initial_wrist_position_base_m'])
    config = json.loads((run / 'config.json').read_text())
    if config.get('episode_schema_version') == SCHEMA_VERSION:
        episode = json.loads((run / 'episode.json').read_text())
        transitions = [json.loads(line) for line in (run / 'transitions.jsonl').read_text().splitlines()]
        validate_transitions(transitions, run, summary['control_hz'])
        if episode['transition_count'] != len(rows) or episode['observation_count'] != len(rows)+1:
            raise ValueError('Episode counts do not match the saved pilot.')
    if abs(metrics['max_abs_tracking_error_xyz_m'][2] - summary['tracking_metrics']['max_abs_tracking_error_xyz_m'][2]) > 1e-9:
        raise ValueError('Summary Z error does not match recorded samples.')
    if not summary['passed']:
        raise ValueError(f'Tracking acceptance failed. See {run / "summary.json"}.')
    if (run / 'motion.gif').stat().st_size == 0:
        raise ValueError('GIF is empty.')
    print(f'PILOT_VERIFIED: 50 samples and PNGs; tracking accepted: {run}')


if __name__ == '__main__':
    check(Path(sys.argv[1]))
