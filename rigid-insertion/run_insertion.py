"""UR5 rigid insertion expert and physical positive/negative controls, Isaac Lab 2.3."""

import argparse
import hashlib
import json
import os
from math import hypot,isfinite
from pathlib import Path
import shutil
import threading
import traceback

from isaaclab.app import AppLauncher
from dataset_manifest import CONTRACT,get_case,load_manifest
from task_math import tilt_quaternion,toward_identity

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--scenario',choices=('aligned','rim','filled'),default='aligned')
parser.add_argument('--offset-x-mm',type=float,default=0.0)
parser.add_argument('--offset-y-mm',type=float,default=0.0)
parser.add_argument('--tilt-x-deg',type=float,default=0.0)
parser.add_argument('--tilt-y-deg',type=float,default=0.0)
parser.add_argument('--manifest',type=Path)
parser.add_argument('--scenario-id')
AppLauncher.add_app_launcher_args(parser)
args=parser.parse_args()
dataset_case=None
manifest_sha=None
if bool(args.manifest)!=bool(args.scenario_id):
    parser.error('Use --manifest and --scenario-id together.')
if args.manifest:
    manifest,manifest_sha=load_manifest(args.manifest)
    dataset_case=get_case(manifest,args.scenario_id)
    for key,value in dataset_case['parameters'].items(): setattr(args,key,value)
    args.scenario='aligned'
try:
    requested_initial_q=tilt_quaternion(args.tilt_x_deg,args.tilt_y_deg)
except ValueError as error:
    parser.error(str(error))
if not args.enable_cameras:
    parser.error('Use --enable_cameras.')
if not all(isfinite(v) for v in (args.offset_x_mm,args.offset_y_mm)) or hypot(args.offset_x_mm,args.offset_y_mm)>4:
    parser.error('Use a finite initial fixture offset within 4 mm radially.')
app=AppLauncher(args).app

import torch
from PIL import Image
from isaacsim.core.utils.stage import get_current_stage
import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg,AssetBaseCfg
from isaaclab.controllers import DifferentialIKController,DifferentialIKControllerCfg
from isaaclab.scene import InteractiveScene,InteractiveSceneCfg
from isaaclab.sensors import CameraCfg,ContactSensorCfg
from isaaclab.utils import configclass
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR
from isaaclab.utils.math import matrix_from_quat,quat_apply,quat_inv,subtract_frame_transforms

from episode import ACTION_NAMES,SCHEMA_VERSION,observation,pose_delta,validate_transitions
from scene_geometry import DOWN_Q,build_geometry
from task_math import TaskSpec,expert_targets,insertion_metrics

SPEC=TaskSpec()
DT=1/SPEC.physics_hz
SUBSTEPS=SPEC.physics_hz//SPEC.control_hz
JOINT_START={'shoulder_pan_joint':0.0,'shoulder_lift_joint':-1.25,'elbow_joint':1.55,
             'wrist_1_joint':-1.35,'wrist_2_joint':-1.57,'wrist_3_joint':0.0}


@configclass
class InsertionScene(InteractiveSceneCfg):
    ground=AssetBaseCfg(prim_path='/World/Ground',spawn=sim_utils.GroundPlaneCfg())
    light=AssetBaseCfg(prim_path='/World/Light',spawn=sim_utils.DomeLightCfg(intensity=3000))
    robot=ArticulationCfg(
        prim_path='{ENV_REGEX_NS}/Robot',
        spawn=sim_utils.UsdFileCfg(
            usd_path=f'{ISAAC_NUCLEUS_DIR}/Robots/UniversalRobots/ur5/ur5.usd',
            articulation_props=sim_utils.ArticulationRootPropertiesCfg(fix_root_link=True,enabled_self_collisions=False,
                                                                      solver_position_iteration_count=16,solver_velocity_iteration_count=4),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(disable_gravity=False),
        ),
        init_state=ArticulationCfg.InitialStateCfg(joint_pos=JOINT_START),
        actuators={'arm':ImplicitActuatorCfg(joint_names_expr=list(JOINT_START),stiffness=800.0,damping=60.0)},
    )
    camera=CameraCfg(prim_path='{ENV_REGEX_NS}/Camera',width=640,height=480,data_types=['rgb'],update_period=0,
                     spawn=sim_utils.PinholeCameraCfg(focal_length=30.0,clipping_range=(.03,10.0)))
    contacts=ContactSensorCfg(prim_path='{ENV_REGEX_NS}/Robot/PegTool',update_period=0,history_length=1)


def write_json(path,data):
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def main():
    (args.output/'rgb').mkdir(parents=True,exist_ok=False)
    sim=sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=DT,device=args.device))
    scene=InteractiveScene(InsertionScene(num_envs=1,env_spacing=2.0))
    geometry=build_geometry(get_current_stage(),args.scenario,SPEC,(args.offset_x_mm/1000,args.offset_y_mm/1000))
    sim.reset()
    robot,camera,contacts=scene['robot'],scene['camera'],scene['contacts']
    print('INSERTION_BODIES',robot.body_names,flush=True)
    print('INSERTION_JOINTS',robot.joint_names,flush=True)
    body_ids,_=robot.find_bodies('PegTool')
    if not robot.is_fixed_base or len(body_ids)!=1 or body_ids[0]==0 or set(robot.joint_names)!=set(JOINT_START):
        raise RuntimeError('Expected a fixed UR5 with a fixed-joint PegTool link and six actuated joints.')
    body_id=body_ids[0]
    tip_offset=torch.tensor([[0,0,SPEC.tip_offset_m]],device=sim.device)
    hole_top=geometry['hole_top_world_m']
    camera.set_world_poses_from_view(torch.tensor([CONTRACT['camera_position_world_m']],device=sim.device),
                                     torch.tensor([CONTRACT['camera_look_at_world_m']],device=sim.device))
    robot.write_joint_state_to_sim(robot.data.default_joint_pos,robot.data.default_joint_vel)
    robot.set_joint_position_target(robot.data.default_joint_pos)
    scene.reset()
    torque_peak=0.0
    torque_clipped=0

    def compensation():
        nonlocal torque_peak,torque_clipped
        raw=robot.root_physx_view.get_gravity_compensation_forces().clone()
        if raw.shape!=robot.data.joint_pos.shape or not bool(torch.isfinite(raw).all()):
            raise RuntimeError('Invalid gravity torque tensor for the augmented UR5.')
        applied=raw.clamp(-robot.data.joint_effort_limits,robot.data.joint_effort_limits)
        torque_peak=max(torque_peak,float(applied.abs().max()))
        torque_clipped+=int(bool((raw!=applied).any()))
        robot.set_joint_effort_target(applied)
        return applied

    def tcp():
        body=robot.data.body_pose_w[:,body_id]
        offset_world=quat_apply(body[:,3:],tip_offset)
        position_world=body[:,:3]+offset_world
        # q_body * RotX(pi); TCP +Z points back toward the wrist.
        tcp_quat_world=torch.stack((-body[:,4],body[:,3],body[:,6],-body[:,5]),dim=-1)
        root=robot.data.root_pose_w
        position_base,quat_base=subtract_frame_transforms(root[:,:3],root[:,3:],position_world,tcp_quat_world)
        return position_base,quat_base,position_world,body[:,3:],offset_world

    for _ in range(60):
        compensation()
        scene.write_data_to_sim()
        sim.step()
        scene.update(DT)
    p,q,p_world,q_world,_=tcp()
    start=p[0].tolist()
    start_metrics=insertion_metrics(p_world[0].tolist(),q_world[0].tolist(),hole_top,SPEC)
    if abs(start_metrics['depth_m']+SPEC.approach_gap_m)>.002 or start_metrics['axis_tilt_deg']>.2:
        raise RuntimeError(f'Tool mounting/TCP calibration differs from expected start: {start_metrics}')
    # World and base coincide in this scene; reject accidental changes rather than silently mixing frames.
    if float(robot.data.root_pose_w[0,:3].abs().max())>1e-6 or abs(float(robot.data.root_pose_w[0,3]))<.999999:
        raise RuntimeError('This first expert requires the documented identity base-to-world transform.')
    controller=DifferentialIKController(DifferentialIKControllerCfg(command_type='pose',use_relative_mode=False,ik_method='dls'),
                                         num_envs=1,device=sim.device)
    limits=robot.data.soft_joint_pos_limits

    def advance_control(target,target_q):
        controller.set_command(torch.tensor([target+target_q],device=sim.device))
        control_peak=0.0
        for substep in range(SUBSTEPS):
            p,q,_,_,offset_world=tcp()
            jacobian=robot.root_physx_view.get_jacobians()[:,body_id-1].clone()
            rx,ry,rz=offset_world[0]
            skew=torch.zeros((1,3,3),device=sim.device)
            skew[0,0,1],skew[0,0,2]=-rz,ry
            skew[0,1,0],skew[0,1,2]=rz,-rx
            skew[0,2,0],skew[0,2,1]=-ry,rx
            jacobian[:,:3]-=skew@jacobian[:,3:]
            rotation=matrix_from_quat(quat_inv(robot.data.root_pose_w[:,3:]))
            jacobian=torch.cat((rotation@jacobian[:,:3],rotation@jacobian[:,3:]),dim=1)
            current=robot.data.joint_pos
            desired=controller.compute(p,q,jacobian,current)
            desired=current+(desired-current).clamp(-.02,.02)
            robot.set_joint_position_target(desired.clamp(limits[...,0],limits[...,1]))
            applied_torque=compensation()
            scene.write_data_to_sim()
            sim.step(render=substep==SUBSTEPS-1)
            scene.update(DT)
            force=contacts.data.net_forces_w[0,0]
            force_norm=float(torch.linalg.vector_norm(force))
            if not torch.isfinite(force).all():
                raise RuntimeError('Non-finite contact signal.')
            control_peak=max(control_peak,force_norm)
        return control_peak,applied_torque,force

    # Physically rotate at fixed tip above the fixture before recording obs[0].
    # Setup samples are excluded from the episode, not synthetic augmentation.
    for i in range(1,41):
        # The calibrated home is nearly identity; use the requested rotation
        # along its shortest arc from identity, then hold for ten steps.
        setup_q=toward_identity(requested_initial_q,1-min(i,30)/30)
        advance_control(start,setup_q)
    p,q,p_world,q_world,_=tcp()
    initial_error=pose_delta(p[0].tolist(),q[0].tolist(),start,requested_initial_q)
    if sum(v*v for v in initial_error[:3])**.5>.0005 or sum(v*v for v in initial_error[3:6])**.5>.15*3.141592653589793/180:
        raise RuntimeError(f'Physical tilt preparation did not converge: {initial_error}')
    planned=expert_targets(p[0].tolist(),hole_top,args.scenario,SPEC,q[0].tolist())
    config={'task_id':CONTRACT['task_id'],'tcp_frame':'tip_z_up_v1','scenario':args.scenario,'spec':SPEC.metadata(),
            'dataset_case':dataset_case,'manifest_sha256':manifest_sha,
            'requested_initial_tcp_quaternion_wxyz':requested_initial_q,
            'measured_initial_tcp_quaternion_wxyz':q[0].tolist(),
            'measured_initial_axis_tilt_deg':insertion_metrics(p_world[0].tolist(),q_world[0].tolist(),hole_top,SPEC)['axis_tilt_deg'],
            'initial_preparation_error':initial_error,'preparation_control_steps':40,
            'geometry':geometry,'control_hz':SPEC.control_hz,'physics_hz':SPEC.physics_hz,
            'joint_names':robot.joint_names,'body_names':robot.body_names,'robot_gravity_disabled':False,
            'gravity_compensation':True,'joint_stiffness':robot.data.joint_stiffness[0].tolist(),
            'joint_damping':robot.data.joint_damping[0].tolist(),'joint_effort_limits_nm':robot.data.joint_effort_limits[0].tolist(),
            'expert_uses_ground_truth':True,'model_used':False,'contact_wrench_validated':False,
            'tool_tip_offset_local_m':[0,0,SPEC.tip_offset_m],
            'camera_intrinsics':camera.data.intrinsic_matrices[0].tolist(),
            'camera_position_world_m':camera.data.pos_w[0].tolist(),
            'camera_orientation_ros_wxyz':camera.data.quat_w_ros[0].tolist()}
    write_json(args.output/'config.json',config)
    if args.manifest: shutil.copyfile(args.manifest,args.output/'dataset_manifest.json')

    def save_frame(relative):
        rgb=camera.data.output['rgb'][0,...,:3].cpu().numpy()
        if rgb.shape!=(480,640,3) or rgb.min()==rgb.max():
            raise RuntimeError('Invalid rendered insertion RGB frame.')
        frame=Image.fromarray(rgb)
        frame.save(args.output/relative)
        return frame

    save_frame('initial_rgb.png')
    rows=[]
    transitions=[]
    previews=[]
    success_streak=0
    longest_streak=0
    contact_steps=0
    peak_contact=0.0
    with (args.output/'steps.jsonl').open('w') as log:
        for step,reference in enumerate(planned):
            if not app.is_running():
                raise RuntimeError('Simulator closed before insertion finished.')
            p,q,_,_,_=tcp()
            before=observation(step/SPEC.control_hz,'initial_rgb.png' if step==0 else f'rgb/{step-1:04d}.png',
                               p[0].tolist(),q[0].tolist(),robot.data.joint_pos[0].tolist(),robot.data.joint_vel[0].tolist())
            target=reference['position']
            target_q=reference['orientation']
            action=pose_delta(p[0].tolist(),q[0].tolist(),target,target_q)
            control_peak,applied_torque,force=advance_control(target,target_q)
            p,q,p_world,q_world,_=tcp()
            metrics=insertion_metrics(p_world[0].tolist(),q_world[0].tolist(),hole_top,SPEC)
            success_streak=success_streak+1 if metrics['instant_success'] else 0
            longest_streak=max(longest_streak,success_streak)
            contact_steps+=int(control_peak>.5)
            peak_contact=max(peak_contact,control_peak)
            relative=f'rgb/{step:04d}.png'
            frame=save_frame(relative)
            if step%3==0: previews.append(frame)
            nxt=observation((step+1)/SPEC.control_hz,relative,p[0].tolist(),q[0].tolist(),
                            robot.data.joint_pos[0].tolist(),robot.data.joint_vel[0].tolist())
            evaluation={'target_pose_base_m_wxyz':target+target_q,
                        'hole_top_world_m':hole_top,'tool_tip_world_m':p_world[0].tolist(),
                        'tool_orientation_world_wxyz':q_world[0].tolist(),'insertion':metrics,
                        'peg_tip_pose_in_hole_m_wxyz':[v-origin for v,origin in zip(p_world[0].tolist(),hole_top)]+q[0].tolist(),
                        'contact':{'status':'contact' if control_peak>.5 else 'no_contact_detected',
                                   'normal_force_world_n_raw':force.tolist(),'peak_normal_force_n_raw':control_peak,
                                   'wrench_validated':False,'wrench':None}}
            row={'step':step,'time_s':(step+1)/SPEC.control_hz,'rgb':relative,'phase':reference['phase'],
                 'observation_before_action':before,'action_delta_base':action,
                 'tcp_position_base_m':p[0].tolist(),'tcp_orientation_base_wxyz':q[0].tolist(),
                 'joint_positions_rad':robot.data.joint_pos[0].tolist(),'joint_velocities_rad_s':robot.data.joint_vel[0].tolist(),
                 'gravity_compensation_applied_nm':applied_torque[0].tolist(),'evaluation':evaluation}
            log.write(json.dumps(row,allow_nan=False)+'\n')
            log.flush()
            rows.append(row)
            transitions.append({'step':step,'observation':before,'action':action,'next_observation':nxt,
                                'is_first':step==0,'is_last':step==len(planned)-1,'evaluation':evaluation})
            if (step+1)%25==0:
                print('INSERTION_STEP',step+1,'depth_mm',round(metrics['depth_m']*1000,3),'contact_raw_N',round(control_peak,3),flush=True)
    validate_transitions(transitions,args.output,SPEC.control_hz)
    (args.output/'transitions.jsonl').write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in transitions))
    task_success=success_streak>=SPEC.success_hold_steps
    write_json(args.output/'episode.json',{
        'schema_version':SCHEMA_VERSION,'task_id':config['task_id'],'language_instruction':'Insert the peg into the hole.',
        'exporter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'transition_count':len(rows),'observation_count':len(rows)+1,'control_hz':SPEC.control_hz,
        'action_names':ACTION_NAMES,'action_normalized':False,'native_action_chunk_length':1,
        'rotation_convention':'base-frame rotvec, q_target = q_delta * q_observed, wxyz quaternions',
        'proprio_names':['tcp_x_m','tcp_y_m','tcp_z_m','tcp_rx_rad','tcp_ry_rad','tcp_rz_rad','fixed_gripper_0','fixed_gripper_1'],
        'joint_names':robot.joint_names,'base_pose_world_m_wxyz':robot.data.root_pose_w[0].tolist(),
        'split':dataset_case['split'] if dataset_case else 'geometry_validation_only',
        'scenario_id':dataset_case['id'] if dataset_case else None,'manifest_sha256':manifest_sha,
        'normalization':{'fit_on':'training insertion episodes only','action_normalization_mask':[True]*6+[False],'statistics_fitted':False},
        'tool':{'kind':'fixed_massive_peg','controlled_link':'PegTool','tcp_offset_tool_m':[0,0,SPEC.tip_offset_m],
                'tcp_offset_m_wxyz':[0,0,SPEC.tip_offset_m,*DOWN_Q],
                'axis_convention':'Tool body +Z points down shaft; TCP +Z points toward wrist.',
                'mount_quaternion_wxyz':geometry['mount_quaternion_wxyz'],'mass_properties':geometry['mass_properties']},
        'camera':{key:config[key] for key in ('camera_intrinsics','camera_position_world_m','camera_orientation_ros_wxyz')},
        'robot_gravity_disabled':False,'gravity_compensation':True,'expert_uses_ground_truth':True,
        'eligible_for_insertion_dataset':bool(dataset_case and task_success),
        'eligible_for_insertion_training':bool(dataset_case and task_success and dataset_case['split']=='train'),
        'exclusion_reason':None if dataset_case and task_success else 'Physics validation or failed episode; excluded from dataset.',
        'contact_wrench_validated':False,
    })
    previews[0].save(args.output/'motion.gif',save_all=True,append_images=previews[1:],duration=150,loop=0)
    max_depth=max(row['evaluation']['insertion']['depth_m'] for row in rows)
    blocked=not task_success and max_depth<.002 and peak_contact>.5
    passed=task_success if args.scenario=='aligned' else blocked
    summary={'scenario':args.scenario,'frame_count':len(rows),'observation_count':len(rows)+1,
             'task_success':task_success,'expected_task_success':args.scenario=='aligned',
             'longest_success_streak':longest_streak,'final_success_streak':success_streak,'max_insertion_depth_m':max_depth,
             'final_metrics':rows[-1]['evaluation']['insertion'],
             'commanded_final_depth_m':SPEC.insertion_depth_m,'contact_control_steps':contact_steps,
             'peak_contact_normal_force_n_raw':peak_contact,'contact_wrench_validated':False,
             'gravity_compensation_peak_nm':torque_peak,'gravity_compensation_clipped_steps':torque_clipped,
             'validation_passed':passed and torque_clipped==0}
    write_json(args.output/'summary.json',summary)
    print('INSERTION_SUMMARY',json.dumps(summary),flush=True)
    if not summary['validation_passed']:
        raise RuntimeError(f'Insertion validation failed: {summary}')


try:
    main()
except BaseException:
    traceback.print_exc()
    raise
finally:
    def watchdog():
        print('INSERTION_CLOSE_TIMEOUT',flush=True)
        os._exit(124)
    timer=threading.Timer(45,watchdog)
    timer.daemon=True
    timer.start()
    app.close(wait_for_replicator=False,skip_cleanup=True)
    timer.cancel()
