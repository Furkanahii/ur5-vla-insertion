"""Base-frame position targets for the UR5 camera and control pilot."""

import json
from math import dist, isfinite
from pathlib import Path

CONTROL_HZ = 20
RAMP_STEPS = 30
HOLD_STEPS = 20
MAX_DISPLACEMENT_M = 0.08


def targets(initial: list[float], dx_m: float, replay: Path | None = None, *, hold: bool = False) -> list[list[float]]:
    if replay is None:
        if hold:
            return [list(initial) for _ in range(RAMP_STEPS + HOLD_STEPS)]
        if not isfinite(dx_m) or not 0.01 <= abs(dx_m) <= MAX_DISPLACEMENT_M:
            raise ValueError('Choose an X displacement from 0.01 m to 0.08 m in either direction.')
        return [
            [initial[0] + dx_m * min(step / RAMP_STEPS, 1.0), initial[1], initial[2]]
            for step in range(1, RAMP_STEPS + HOLD_STEPS + 1)
        ]

    with replay.open() as stream:
        recorded = [json.loads(line) for line in stream]
    if len(recorded) != RAMP_STEPS + HOLD_STEPS:
        raise ValueError('Replay requires a complete 50-step pilot recording.')
    positions = []
    previous = initial
    for index, entry in enumerate(recorded):
        position = entry['target_position_base_m']
        if (
            entry['step'] != index
            or abs(entry['time_s'] - (index + 1) / CONTROL_HZ) > 1e-6
            or len(position) != 3
            or not all(isfinite(value) for value in position)
            or dist(position, initial) > MAX_DISPLACEMENT_M + 0.002
            or dist(position, previous) > 0.005
        ):
            raise ValueError(f'Invalid replay target or timestamp at step {index}.')
        positions.append(position)
        previous = position
    return positions


def orientations(initial: list[float], replay: Path | None = None) -> list[list[float]]:
    """Replay the recorded orientation, rather than substituting a new initial pose."""
    if replay is None:
        return [list(initial) for _ in range(RAMP_STEPS + HOLD_STEPS)]
    rows = [json.loads(line) for line in replay.read_text().splitlines()]
    if len(rows) != RAMP_STEPS + HOLD_STEPS:
        raise ValueError('Replay requires a complete 50-step pilot recording.')
    result = []
    for index, row in enumerate(rows):
        quaternion = row['target_orientation_base_wxyz']
        if len(quaternion) != 4 or not all(isfinite(x) for x in quaternion) or abs(sum(x * x for x in quaternion) - 1) > 1e-3:
            raise ValueError(f'Invalid replay orientation at step {index}.')
        result.append(quaternion)
    return result
