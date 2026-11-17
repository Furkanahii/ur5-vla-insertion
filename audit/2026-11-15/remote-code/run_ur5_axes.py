"""Record a small UR5 wrist motion and synchronized RGB frames in Isaac Lab 2.3."""

import argparse
import json
from math import dist
from pathlib import Path

from isaaclab.app import AppLauncher

from motion import CONTROL_HZ, targets

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--dx-m', type=float, default=0.03)
parser.add_argument('--replay', type=Path, help='steps.jsonl from a previous run of this scene')
parser.add_argument('--ur5-usd', help='Optional local replacement for the NVIDIA UR5 USD')
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if not args.enable_cameras:
    parser.error('Pass --enable_cameras to record the RGB stream.')
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
            rigid_props=sim_utils.RigidBodyPropertiesCfg(disable_gravity=True),
            articulation_props=sim_utils.ArticulationRootPropertiesCfg(fix_root_link=True),
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
    for _ in range(12):
        scene.write_data_to_sim()
        sim.step()
        scene.update(DT)

    def wrist_in_base() -> tuple[torch.Tensor, torch.Tensor]:
        root = robot.data.root_pose_w
        wrist = robot.data.body_pose_w[:, body_id]
        return subtract_frame_transforms(root[:, :3], root[:, 3:], wrist[:, :3], wrist[:, 3:])

    from isaaclab.markers import VisualizationMarkers
    from isaaclab.markers.config import FRAME_MARKER_CFG

    axes_cfg = FRAME_MARKER_CFG.copy()
    axes_cfg.prim_path = '/Visuals/BaseAxes'
    axes_cfg.markers['frame'].scale = (0.3, 0.3, 0.3)
    base_axes = VisualizationMarkers(axes_cfg)
    base_axes.visualize(
        robot.data.root_pose_w[:, :3],
        robot.data.root_pose_w[:, 3:],
    )

    initial_position, initial_orientation = wrist_in_base()
    initial = initial_position[0].tolist()
    orientation = initial_orientation.clone()
    commands = targets(initial, args.dx_m, args.replay)
    controller = DifferentialIKController(
        DifferentialIKControllerCfg(command_type='pose', use_relative_mode=False, ik_method='dls'),
        num_envs=1,
        device=sim.device,
    )
    limits = robot.data.soft_joint_pos_limits
    frames = []
    previous = initial
    with (args.output / 'steps.jsonl').open('w') as log:
        for step, target in enumerate(commands):
            if not app.is_running():
                raise RuntimeError('Simulation closed before the pilot finished.')
            command = torch.cat((torch.tensor([target], device=sim.device), orientation), dim=-1)
            controller.set_command(command)
            for substep in range(PHYSICS_STEPS):
                position, quat = wrist_in_base()
                jacobian = robot.root_physx_view.get_jacobians()[:, body_id - 1]
                rotation = matrix_from_quat(quat_inv(robot.data.root_pose_w[:, 3:]))
                jacobian = torch.cat((rotation @ jacobian[:, :3], rotation @ jacobian[:, 3:]), dim=1)
                joints = robot.data.joint_pos
                desired = controller.compute(position, quat, jacobian, joints)
                desired = joints + (desired - joints).clamp(-0.04, 0.04)
                robot.set_joint_position_target(desired.clamp(limits[..., 0], limits[..., 1]))
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
                'target_position_base_m': target,
                'target_orientation_base_wxyz': orientation[0].tolist(),
                'target_increment_base_m': [value - old for value, old in zip(target, previous)],
                'wrist_position_base_m': measured,
                'wrist_orientation_base_wxyz': quat[0].tolist(),
                'joint_positions_rad': robot.data.joint_pos[0].tolist(),
            }
            log.write(json.dumps(record, allow_nan=False) + '\n')
            previous = target

    frames[0].save(
        args.output / 'motion.gif', save_all=True, append_images=frames[1:],
        duration=1000 // CONTROL_HZ, loop=0,
    )
    error = dist(measured, commands[-1])
    requested_distance = dist(initial, commands[-1])
    observed_distance = dist(initial, measured)
    replay_endpoint_error = None
    if args.replay is not None:
        reference = json.loads(args.replay.with_name('summary.json').read_text())
        replay_endpoint_error = dist(measured, reference['final_wrist_position_base_m'])
    summary = {
        'diagnostic_robot_gravity_disabled': True,
        'frame_count': len(frames),
        'control_hz': CONTROL_HZ,
        'physics_hz': CONTROL_HZ * PHYSICS_STEPS,
        'wrist_body': WRIST,
        'joint_names': robot.joint_names,
        'camera_intrinsics': camera.data.intrinsic_matrices[0].tolist(),
        'camera_position_world_m': camera.data.pos_w[0].tolist(),
        'camera_orientation_ros_wxyz': camera.data.quat_w_ros[0].tolist(),
        'initial_wrist_position_base_m': initial,
        'final_wrist_position_base_m': measured,
        'final_position_error_m': error,
        'replay_endpoint_difference_m': replay_endpoint_error,
        'passed': (
            error <= 0.012
            and observed_distance >= requested_distance / 2
            and (replay_endpoint_error is None or replay_endpoint_error <= 0.005)
        ),
    }
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps(summary), flush=True)
    if not summary['passed']:
        raise RuntimeError(f'Wrist tracking or replay check failed. See {args.output / "summary.json"}.')


try:
    main()
finally:
    print('CLOSE_BEGIN', flush=True)
    app.close()
    print('CLOSE_END', flush=True)
