"""Verify that the evaluator actually completed all ten smoke-test episodes."""

from pathlib import Path
import sys


def check_run(run: Path) -> None:
    logs = list((run / 'eval-logs').glob('EVAL-libero_10-*.txt'))
    if len(logs) != 1:
        raise SystemExit(f'Expected one evaluation log, found {len(logs)}.')

    lines = logs[0].read_text().splitlines()
    if any('Episode error:' in line for line in lines):
        raise SystemExit(f'The evaluator reported an episode error. See {logs[0]}.')
    if 'Total episodes: 10' not in lines:
        raise SystemExit(f'The evaluator did not report ten completed episodes. See {logs[0]}.')

    videos = list((run / 'rollouts').rglob('*.mp4'))
    if len(videos) != 10 or any(video.stat().st_size == 0 for video in videos):
        raise SystemExit('Expected ten nonempty rollout videos.')

    print('Verified ten completed LIBERO episodes and ten rollout videos.')


if __name__ == '__main__':
    check_run(Path(sys.argv[1]))
