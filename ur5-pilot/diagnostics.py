"""Measure wrist tracking in recorded samples; works without Isaac Lab or NumPy."""

import argparse
import json
from math import acos, degrees, dist, isfinite, sqrt
from pathlib import Path


def vector(value: list[float], size: int) -> list[float]:
    if len(value) != size or not all(isfinite(item) for item in value):
        raise ValueError(f'Expected {size} finite numbers, got {value!r}.')
    return value


def orientation_error_deg(first: list[float], second: list[float]) -> float:
    vector(first, 4)
    vector(second, 4)
    norm = sqrt(sum(x * x for x in first) * sum(x * x for x in second))
    if norm < 1e-12:
        raise ValueError('Quaternion must have nonzero length.')
    # q and -q describe the same orientation.
    cosine = min(1.0, abs(sum(a * b for a, b in zip(first, second))) / norm)
    return degrees(2 * acos(cosine))


def tracking_metrics(records: list[dict], initial: list[float]) -> dict:
    if not records:
        raise ValueError('Recording contains no samples.')
    vector(initial, 3)
    measured = [vector(row['wrist_position_base_m'], 3) for row in records]
    targets = [vector(row['target_position_base_m'], 3) for row in records]
    errors = [[p - t for p, t in zip(position, target)] for position, target in zip(measured, targets)]
    metrics = {
        'sample_count': len(records),
        'max_abs_tracking_error_xyz_m': [max(abs(error[axis]) for error in errors) for axis in range(3)],
        'rms_tracking_error_xyz_m': [
            sqrt(sum(error[axis] ** 2 for error in errors) / len(errors)) for axis in range(3)
        ],
        'max_position_error_m': max(dist(position, target) for position, target in zip(measured, targets)),
        'final_tracking_error_xyz_m': errors[-1],
        'final_displacement_xyz_m': [p - start for p, start in zip(measured[-1], initial)],
        'z_displacement_range_m': [min(p[2] - initial[2] for p in measured), max(p[2] - initial[2] for p in measured)],
    }
    if all('wrist_orientation_base_wxyz' in row and 'target_orientation_base_wxyz' in row for row in records):
        angles = [orientation_error_deg(row['wrist_orientation_base_wxyz'], row['target_orientation_base_wxyz']) for row in records]
        metrics['max_orientation_error_deg'] = max(angles)
        metrics['final_orientation_error_deg'] = angles[-1]
    if all('root_pose_world_m_wxyz' in row for row in records):
        roots = [vector(row['root_pose_world_m_wxyz'], 7) for row in records]
        metrics['max_root_translation_from_first_sample_m'] = max(dist(root[:3], roots[0][:3]) for root in roots)
    if all('joint_position_targets_rad' in row for row in records):
        metrics['max_joint_tracking_error_rad'] = max(
            abs(actual - target)
            for row in records
            for actual, target in zip(vector(row['joint_positions_rad'], 6), vector(row['joint_position_targets_rad'], 6))
        )
    return metrics


def analyze(run: Path) -> dict:
    source = run if run.is_file() else run / 'steps.jsonl'
    records = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    summary_path = source.with_name('summary.json')
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    initial = summary.get('initial_wrist_position_base_m')
    if initial is None:
        if not records:
            raise ValueError('Recording contains no samples.')
        initial = records[0]['target_position_base_m']
    config_path = source.with_name('config.json')
    return {
        'source': str(source.resolve()),
        'initial_reference': 'summary' if 'initial_wrist_position_base_m' in summary else 'first_target (initial pose unavailable)',
        'config': json.loads(config_path.read_text()) if config_path.exists() else None,
        'metrics': tracking_metrics(records, initial),
        'limitation': 'Metrics cover recorded control samples, not unrecorded physics substeps. Gravity cannot be inferred from old logs without configuration.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', type=Path, nargs='+', help='Run folders or steps.jsonl files')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = json.dumps([analyze(run) for run in args.runs], indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(report)
    print(report, end='')
