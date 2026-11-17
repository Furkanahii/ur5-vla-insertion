"""Record a small UR5 wrist motion and synchronized RGB frames in Isaac Lab 2.3."""

import argparse
import json
import os
import threading
import traceback
from math import dist
from pathlib import Path

from isaaclab.app import AppLauncher

from diagnostics import tracking_metrics
from episode import SCHEMA_VERSION, apply_delta, export_run, observation, pose_delta
from motion import CONTROL_HZ, orientations, targets

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--dx-m', type=float, default=0.03)
parser.add_argument('--replay', type=Path, help='steps.jsonl from a previous run of this scene')
parser.add_argument('--replay-actions', action='store_true', help='Reconstruct targets from recorded deltas and current measured pose')
parser.add_argument('--ur5-usd', help='Optional local replacement for the NVIDIA UR5 USD')
parser.add_argument('--disable-gravity', action='store_true', help='Diagnostic only: disable gravity on robot links')
parser.add_argument('--gravity-compensation', action='store_true', help='Keep gravity on and add PhysX gravity feed-forward torques')
parser.add_argument('--motion', choices=('x', 'hold', 'joint-hold'), default='x')
parser.add_argument('--warmup-steps', type=int, default=12)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if not args.enable_cameras:
    parser.error('Pass --enable_cameras to record the RGB stream.')
if not 0 <= args.warmup_steps <= 600:
    parser.error('--warmup-steps must be between 0 and 600 physics steps.')
if args.replay and args.motion != 'x':
    parser.error('Replay uses recorded Cartesian targets; do not combine it with --motion.')
if args.gravity_compensation and args.disable_gravity:
    parser.error('Gravity compensation requires robot gravity to remain enabled.')
if args.replay_actions and args.replay is None:
    parser.error('--replay-actions requires --replay.')
app = AppLauncher(args).app

import torch
from PIL import Image

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg, AssetBaseCfg
from isaaclab.controllers import DifferentialIKController, DifferentialIKControllerCfg
from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
from isaaclab.sensors import CameraCfg
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR
from isaaclab.utils.math import matrix_from_quat, quat_inv, subtract_frame_transforms

PHYSICS_STEPS = 3
DT = 1.0 / (CONTROL_HZ * PHYSICS_STEPS)
WRIST = 'wrist_3_link'
JOINT_START = {
    'shoulder_pan_joint': 0.0,
    'shoulder_lift_joint': -1.25,
    'elbow_joint': 1.55,
    'wrist_1_joint': -1.35,
    'wrist_2_joint': -1.57,
    'wrist_3_joint': 0.0,
}


@configclass
class PilotScene(InteractiveSceneCfg):
    ground = AssetBaseCfg(prim_path='/World/Ground', spawn=sim_utils.GroundPlaneCfg())
    light = AssetBaseCfg(prim_path='/World/Light', spawn=sim_utils.DomeLightCfg(intensity=2500.0))
    robot = ArticulationCfg(
        prim_path='{ENV_REGEX_NS}/Robot',
        spawn=sim_utils.UsdFileCfg(
            usd_path=args.ur5_usd or f'{ISAAC_NUCLEUS_DIR}/Robots/UniversalRobots/ur5/ur5.usd',
            articulation_props=sim_utils.ArticulationRootPropertiesCfg(fix_root_link=True),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(disable_gravity=args.disable_gravity),
        ),
        init_state=ArticulationCfg.InitialStateCfg(joint_pos=JOINT_START),
        actuators={
            'arm': ImplicitActuatorCfg(
                joint_names_expr=list(JOINT_START), stiffness=800.0, damping=60.0,
            ),
        },
    )
    camera = CameraCfg(
        prim_path='{ENV_REGEX_NS}/Camera',
        width=320,
        height=240,
        data_types=['rgb'],
        update_period=0,
        spawn=sim_utils.PinholeCameraCfg(focal_length=20.0, clipping_range=(0.05, 10.0)),
    )


def main() -> None:
    frames_dir = args.output / 'rgb'
    frames_dir.mkdir(parents=True, exist_ok=False)
    sim = sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=DT, device=args.device))
    scene = InteractiveScene(PilotScene(num_envs=1, env_spacing=2.0))
    sim.reset()
    robot, camera = scene['robot'], scene['camera']
    print('PILOT_SIM_READY', flush=True)
    body_ids, _ = robot.find_bodies(WRIST)
    if not robot.is_fixed_base or len(body_ids) != 1 or body_ids[0] == 0:
        raise RuntimeError(f'Expected a fixed UR5 with one {WRIST}; found {robot.body_names}.')
    if set(robot.joint_names) != set(JOINT_START):
        raise RuntimeError(f'Unexpected UR5 joints: {robot.joint_names}.')
    body_id = body_ids[0]
    camera.set_world_poses_from_view(
        torch.tensor([[1.25, 1.05, 0.95]], device=sim.device),
        torch.tensor([[0.0, 0.0, 0.38]], device=sim.device),
    )
    robot.write_joint_state_to_sim(robot.data.default_joint_pos, robot.data.default_joint_vel)
    robot.set_joint_position_target(robot.data.default_joint_pos)
    scene.reset()
    compensation_peak_nm = 0.0
    compensation_clipped_steps = 0

    def apply_gravity_compensation() -> tuple[torch.Tensor, torch.Tensor]:
        nonlocal compensation_peak_nm, compensation_clipped_steps
        raw = torch.zeros_like(robot.data.joint_pos)
        if args.gravity_compensation:
            raw = robot.root_physx_view.get_gravity_compensation_forces().clone()
            if raw.shape != robot.data.joint_pos.shape or not bool(torch.isfinite(raw).all()):
                raise RuntimeError(f'Invalid fixed-base gravity torque tensor: {raw.shape}.')
        effort_limits = robot.data.joint_effort_limits
        applied = raw.clamp(-effort_limits, effort_limits)
        compensation_clipped_steps += int(bool((raw != applied).any()))
        compensation_peak_nm = max(compensation_peak_nm, float(applied.abs().max()))
        robot.set_joint_effort_target(applied)
        return raw, applied

    def wrist_in_base() -> tuple[torch.Tensor, torch.Tensor]:
        root = robot.data.root_pose_w
        wrist = robot.data.body_pose_w[:, body_id]
        return subtract_frame_transforms(root[:, :3], root[:, 3:], wrist[:, :3], wrist[:, 3:])

    config = {
        'schema_version': 3,
        'episode_schema_version': SCHEMA_VERSION,
        'robot_gravity_disabled': args.disable_gravity,
        'gravity_compensation': args.gravity_compensation,
        'motion': args.motion,
        'warmup_steps': args.warmup_steps,
        'physics_hz': CONTROL_HZ * PHYSICS_STEPS,
        'control_hz': CONTROL_HZ,
        'wrist_body': WRIST,
        'ur5_usd': scene.cfg.robot.spawn.usd_path,
        'initial_joint_positions_rad': robot.data.default_joint_pos[0].tolist(),
        'joint_names': robot.joint_names,
        'joint_stiffness': robot.data.joint_stiffness[0].tolist(),
        'joint_damping': robot.data.joint_damping[0].tolist(),
        'joint_effort_limits_nm': robot.data.joint_effort_limits[0].tolist(),
        'joint_velocity_limits_rad_s': robot.data.joint_vel_limits[0].tolist(),
        'soft_joint_position_limits_rad': robot.data.soft_joint_pos_limits[0].tolist(),
        'max_ik_joint_increment_rad_per_physics_step': 0.04,
        'replay_source': str(args.replay) if args.replay else None,
        'replay_mode': ('delta' if args.replay_actions else 'absolute') if args.replay else None,
    }
    if args.replay and args.replay.with_name('config.json').exists():
        source_config = json.loads(args.replay.with_name('config.json').read_text())
        for key in (
            'robot_gravity_disabled', 'gravity_compensation', 'warmup_steps', 'physics_hz', 'control_hz', 'wrist_body',
            'ur5_usd', 'initial_joint_positions_rad', 'joint_names', 'joint_stiffness', 'joint_damping',
            'joint_effort_limits_nm', 'joint_velocity_limits_rad_s', 'soft_joint_position_limits_rad',
        ):
            source_value = source_config.get(key, False) if key == 'gravity_compensation' else source_config[key]
            if config[key] != source_value:
                raise ValueError(f'Replay configuration differs from recording: {key}.')
        if source_config['motion'] == 'joint-hold':
            raise ValueError('Joint-hold diagnostic is not a Cartesian IK replay recording.')
    (args.output / 'config.json').write_text(json.dumps(config, indent=2, allow_nan=False) + '\n')
    before_warmup = wrist_in_base()[0][0].tolist()
    for _ in range(args.warmup_steps):
        apply_gravity_compensation()
        scene.write_data_to_sim()
        sim.step()
        scene.update(DT)

    initial_position, initial_orientation = wrist_in_base()
    initial = initial_position[0].tolist()
    commands = targets(initial, args.dx_m, args.replay, hold=args.motion != 'x')
    command_orientations = orientations(initial_orientation[0].tolist(), args.replay)
    replay_actions = None
    if args.replay_actions:
        replay_actions = [json.loads(line)['action_delta_base'] for line in args.replay.read_text().splitlines()]
    initial_rgb = camera.data.output['rgb'][0, ..., :3].cpu().numpy()
    if initial_rgb.shape != (240, 320, 3) or initial_rgb.max() == initial_rgb.min():
        raise RuntimeError('Initial observation did not contain a rendered RGB image.')
    Image.fromarray(initial_rgb).save(args.output / 'initial_rgb.png')
    controller = DifferentialIKController(
        DifferentialIKControllerCfg(command_type='pose', use_relative_mode=False, ik_method='dls'),
        num_envs=1,
        device=sim.device,
    )
    limits = robot.data.soft_joint_pos_limits
    frames = []
    records = []
    fixed_joint_targets = robot.data.default_joint_pos.clone()
    previous = initial
    with (args.output / 'steps.jsonl').open('w') as log:
        for step, target in enumerate(commands):
            if not app.is_running():
                raise RuntimeError('Simulation closed before the pilot finished.')
            before_position, before_quat = wrist_in_base()
            before_observation = observation(
                step / CONTROL_HZ,
                'initial_rgb.png' if step == 0 else f'rgb/{step-1:04d}.png',
                before_position[0].tolist(), before_quat[0].tolist(),
                robot.data.joint_pos[0].tolist(), robot.data.joint_vel[0].tolist(),
            )
            if replay_actions is not None:
                target, command_orientations[step] = apply_delta(
                    before_position[0].tolist(), before_quat[0].tolist(), replay_actions[step],
                )
                commands[step] = target
            orientation = torch.tensor([command_orientations[step]], device=sim.device)
            action = pose_delta(before_position[0].tolist(), before_quat[0].tolist(), target, orientation[0].tolist())
            command = torch.cat((torch.tensor([target], device=sim.device), orientation), dim=-1)
            controller.set_command(command)
            increment_clipped = False
            limits_clipped = False
            for substep in range(PHYSICS_STEPS):
                if args.motion == 'joint-hold':
                    desired = fixed_joint_targets
                else:
                    position, quat = wrist_in_base()
                    jacobian = robot.root_physx_view.get_jacobians()[:, body_id - 1]
                    rotation = matrix_from_quat(quat_inv(robot.data.root_pose_w[:, 3:]))
                    jacobian = torch.cat((rotation @ jacobian[:, :3], rotation @ jacobian[:, 3:]), dim=1)
                    joints = robot.data.joint_pos
                    raw_desired = controller.compute(position, quat, jacobian, joints)
                    increment_clipped |= bool(((raw_desired - joints).abs() > 0.04).any())
                    desired = joints + (raw_desired - joints).clamp(-0.04, 0.04)
                joint_target = desired.clamp(limits[..., 0], limits[..., 1])
                limits_clipped |= bool((joint_target != desired).any())
                robot.set_joint_position_target(joint_target)
                raw_compensation, applied_compensation = apply_gravity_compensation()
                scene.write_data_to_sim()
                sim.step(render=substep == PHYSICS_STEPS - 1)
                scene.update(DT)

            position, quat = wrist_in_base()
            rgb = camera.data.output['rgb'][0, ..., :3].cpu().numpy()
            if rgb.shape != (240, 320, 3) or rgb.max() == rgb.min():
                raise RuntimeError(f'Expected a rendered RGB frame at step {step}; got {rgb.shape}.')
            frame = Image.fromarray(rgb)
            frame_path = Path('rgb') / f'{step:04d}.png'
            frame.save(args.output / frame_path)
            frames.append(frame)
            measured = position[0].tolist()
            record = {
                'step': step,
                'time_s': (step + 1) / CONTROL_HZ,
                'rgb': frame_path.as_posix(),
                'observation_before_action': before_observation,
                'action_delta_base': action,
                'target_position_base_m': target,
                'target_orientation_base_wxyz': orientation[0].tolist(),
                'target_increment_base_m': [value - old for value, old in zip(target, previous)],
                'wrist_position_base_m': measured,
                'wrist_orientation_base_wxyz': quat[0].tolist(),
                'joint_positions_rad': robot.data.joint_pos[0].tolist(),
                'joint_position_targets_rad': joint_target[0].tolist(),
                'joint_velocities_rad_s': robot.data.joint_vel[0].tolist(),
                'gravity_compensation_raw_nm': raw_compensation[0].tolist(),
                'gravity_compensation_applied_nm': applied_compensation[0].tolist(),
                'root_pose_world_m_wxyz': robot.data.root_pose_w[0].tolist(),
                'wrist_pose_world_m_wxyz': robot.data.body_pose_w[0, body_id].tolist(),
                'ik_increment_clipped': increment_clipped,
                'joint_limits_clipped': limits_clipped,
            }
            log.write(json.dumps(record, allow_nan=False) + '\n')
            log.flush()
            records.append(record)
            previous = target
            if (step + 1) % 10 == 0:
                print(f'PILOT_STEP {step + 1}/{len(commands)}', flush=True)

    frames[0].save(
        args.output / 'motion.gif', save_all=True, append_images=frames[1:],
        duration=1000 // CONTROL_HZ, loop=0,
    )
    error = dist(measured, commands[-1])
    requested_distance = dist(initial, commands[-1])
    observed_distance = dist(initial, measured)
    metrics = tracking_metrics(records, initial)
    replay_endpoint_error = None
    if args.replay is not None:
        reference = json.loads(args.replay.with_name('summary.json').read_text())
        replay_endpoint_error = dist(measured, reference['final_wrist_position_base_m'])
    summary = {
        'frame_count': len(frames),
        'control_hz': CONTROL_HZ,
        'physics_hz': CONTROL_HZ * PHYSICS_STEPS,
        'wrist_body': WRIST,
        'joint_names': robot.joint_names,
        'camera_intrinsics': camera.data.intrinsic_matrices[0].tolist(),
        'camera_position_world_m': camera.data.pos_w[0].tolist(),
        'camera_orientation_ros_wxyz': camera.data.quat_w_ros[0].tolist(),
        'initial_wrist_position_base_m': initial,
        'wrist_position_before_warmup_base_m': before_warmup,
        'warmup_displacement_xyz_m': [value - old for value, old in zip(initial, before_warmup)],
        'final_wrist_position_base_m': measured,
        'final_position_error_m': error,
        'replay_endpoint_difference_m': replay_endpoint_error,
        'tracking_metrics': metrics,
        'ik_increment_clipped_control_steps': sum(row['ik_increment_clipped'] for row in records),
        'joint_limits_clipped_control_steps': sum(row['joint_limits_clipped'] for row in records),
        'gravity_compensation_peak_nm': compensation_peak_nm,
        'gravity_compensation_clipped_physics_steps': compensation_clipped_steps,
        'acceptance_limits': {'final_position_error_m': 0.001 if args.gravity_compensation else 0.012, 'max_sampled_abs_z_error_m': 0.001 if args.gravity_compensation else 0.012, 'replay_endpoint_difference_m': 0.005},
        'passed': (
            error <= (0.001 if args.gravity_compensation else 0.012)
            and metrics['max_abs_tracking_error_xyz_m'][2] <= (0.001 if args.gravity_compensation else 0.012)
            and (not args.gravity_compensation or (
                abs(initial[2] - before_warmup[2]) <= 0.001
                and metrics['max_orientation_error_deg'] <= 1.0
                and compensation_clipped_steps == 0
            ))
            and observed_distance >= requested_distance / 2
            and (replay_endpoint_error is None or replay_endpoint_error <= 0.005)
        ),
    }
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    export_run(args.output)
    print('PILOT_SUMMARY ' + json.dumps(summary, allow_nan=False), flush=True)
    if not summary['passed']:
        raise RuntimeError(f'Wrist tracking or replay check failed. See {args.output / "summary.json"}.')


try:
    main()
except BaseException:
    traceback.print_exc()
    raise
finally:
    # All PNG/JSON/GIF writes above are closed synchronously. Isaac Sim 5.1's
    # full plugin cleanup hangs here; use its documented immediate shutdown.
    # The host checks artifacts independently because fast exit can return 0.
    def shutdown_timeout() -> None:
        print('PILOT_CLOSE_TIMEOUT: shutdown exceeded 45 seconds', flush=True)
        os._exit(124)

    print('PILOT_CLOSE_BEGIN', flush=True)
    close_watchdog = threading.Timer(45, shutdown_timeout)
    close_watchdog.daemon = True
    close_watchdog.start()
    app.close(wait_for_replicator=False, skip_cleanup=True)
    close_watchdog.cancel()
    print('PILOT_CLOSE_END', flush=True)
