"""Render measured pilot data; accepts any number of run directories."""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

runs = [Path(value) for value in sys.argv[1:]]
fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True, constrained_layout=True)
for run in runs:
    rows = [json.loads(line) for line in (run / 'steps.jsonl').read_text().splitlines()]
    config_file = run / 'config.json'
    config = json.loads(config_file.read_text()) if config_file.exists() else {}
    label = run.name
    if config:
        label += f" | {config['motion']} | gravity {'off' if config['robot_gravity_disabled'] else 'on'}"
    times = [row['time_s'] for row in rows]
    for axis, plot in enumerate(axes):
        errors = [1000 * (row['wrist_position_base_m'][axis] - row['target_position_base_m'][axis]) for row in rows]
        plot.plot(times, errors, label=label, linewidth=1.8)
for axis, plot in zip('XYZ', axes):
    plot.axhline(0, color='#687078', linewidth=.8)
    plot.set_ylabel(f'{axis} tracking error (mm)')
    plot.grid(alpha=.2)
axes[0].legend(fontsize=8, loc='best')
axes[-1].set_xlabel('Simulation time (s), sampled at 20 Hz')
fig.suptitle('UR5 wrist tracking: measured position minus target')
output = Path(__file__).parent / ('ur5-comparison.png' if len(runs) > 1 else 'ur5-first-record.png')
fig.savefig(output, dpi=160)
print(output)
