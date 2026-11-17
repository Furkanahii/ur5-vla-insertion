"""Check one allocated GPU and render one LIBERO observation without a model."""

import os

import imageio.v2 as imageio
import imageio_ffmpeg
import torch


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit('PyTorch cannot see CUDA. Check the Slurm GPU request and the driver.')

    gpu = torch.cuda.get_device_properties(0)
    if gpu.major < 8 or not torch.cuda.is_bf16_supported():
        raise SystemExit(f'{gpu.name} does not provide the native BF16 used by this checkpoint.')
    if gpu.total_memory < 20 * 1024**3:
        raise SystemExit(f'{gpu.name} has too little VRAM for this two-camera evaluation.')

    sample = torch.ones((4, 4), dtype=torch.bfloat16, device='cuda')
    if (sample @ sample)[0, 0].item() != 4.0:
        raise RuntimeError('The CUDA BF16 matrix multiplication returned an unexpected result.')
    print(f'PyTorch {torch.__version__}, CUDA {torch.version.cuda}, {gpu.name}')

    from libero.libero import benchmark, get_libero_path
    from libero.libero.envs import OffScreenRenderEnv

    suite = benchmark.get_benchmark_dict()['libero_10']()
    task = suite.get_task(0)
    env = OffScreenRenderEnv(
        bddl_file_name=os.path.join(get_libero_path('bddl_files'), task.problem_folder, task.bddl_file),
        camera_heights=256,
        camera_widths=256,
    )
    try:
        env.seed(0)
        env.reset()
        observation = env.set_init_state(suite.get_task_init_states(0)[0])
        for key, filename in (
            ('agentview_image', 'agentview.png'),
            ('robot0_eye_in_hand_image', 'wrist.png'),
        ):
            frame = observation[key]
            if frame.shape != (256, 256, 3) or frame.min() == frame.max():
                raise RuntimeError(f'Unexpected image from {key}: {frame.shape}')
            imageio.imwrite(filename, frame[::-1, ::-1])
    finally:
        env.close()

    print(f'FFmpeg {imageio_ffmpeg.get_ffmpeg_version()}')
    print(f'LIBERO task rendered: {task.language}')


if __name__ == '__main__':
    main()
