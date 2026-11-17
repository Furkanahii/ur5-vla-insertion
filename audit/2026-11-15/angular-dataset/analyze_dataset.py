"""Local analysis of the 12 completed, frozen angular insertion cases."""
import contextlib
import io
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'data-adapter'))
from adapter_core import collect_episodes

array=sys.argv[1]
output=Path(__file__).resolve().parent
runs=[ROOT/'rigid-insertion'/'runs'/f'{array}_{i}' for i in range(12)]
capture=io.StringIO()
with contextlib.redirect_stdout(capture):
    episodes,manifest_sha=collect_episodes(ROOT/'rigid-insertion'/'pilot_manifest.json',runs)
sources={ (run/'source.sha256').read_text() for run in runs }
if len(sources)!=1: raise ValueError('Source changed between array cases.')
records=[]
image_count=0
camera_poses=set()
colors={'train':'#2878b5','validation':'#ee8c32','test':'#329a69'}
fig,axes=plt.subplots(1,2,figsize=(12,4.3),layout='constrained')
for episode in episodes:
    run=episode['run']
    config=json.loads((run/'config.json').read_text())
    summary=json.loads((run/'summary.json').read_text())
    camera_poses.add(tuple(config['camera_position_world_m']+config['camera_orientation_ros_wxyz']))
    for relative in ['initial_rgb.png']+[f'rgb/{i:04d}.png' for i in range(150)]:
        with Image.open(run/relative) as image: image.verify()
        image_count+=1
    t=[0]+[row['next_observation']['time_s'] for row in episode['transitions']]
    depth=[(config['geometry']['hole_top_world_m'][2]-episode['transitions'][0]['observation']['tcp_position_base_m'][2])*1000]
    depth += [row['evaluation']['insertion']['depth_m']*1000 for row in episode['transitions']]
    tilt=[config['measured_initial_axis_tilt_deg']]+[row['evaluation']['insertion']['axis_tilt_deg'] for row in episode['transitions']]
    for ax,values in zip(axes,(depth,tilt)):
        ax.plot(t,values,color=colors[episode['split']],alpha=.65,lw=1.4)
    records.append({'run_id':run.name,'scenario_id':episode['id'],'split':episode['split'],
                    'parameters':config['dataset_case']['parameters'],
                    'measured_initial_axis_tilt_deg':tilt[0],
                    'axis_tilt_after_alignment_deg':tilt[30],
                    'task_success':summary['task_success'],'final_metrics':summary['final_metrics'],
                    'final_success_streak':summary['final_success_streak'],
                    'gravity_compensation_clipped_steps':summary['gravity_compensation_clipped_steps']})
for ax in axes:
    ax.axvline(1.5,color='#777777',ls=':',lw=1)
    ax.set_xlabel('Simulation time (s)')
    ax.grid(alpha=.18)
axes[0].set(title='Measured peg-tip depth',ylabel='Depth below hole mouth (mm)')
axes[0].axhline(18,color='#333333',ls='--',lw=1)
axes[0].text(3,18.7,'Success depth: 18 mm',fontsize=8,color='#444444')
axes[1].set(title='Measured shaft tilt: align before descent',ylabel='Angle to hole axis (degrees)')
axes[1].axhline(1,color='#333333',ls='--',lw=1)
axes[1].legend(handles=[Line2D([0],[0],color=c,label=s) for s,c in colors.items()],loc='upper right')
fig.suptitle('UR5 scripted expert — 12 frozen cases (8 train / 2 validation / 2 test)',fontsize=12)
fig.savefig(output/'angular-validation.png',dpi=170)
plt.close(fig)
sample=episodes[6]
fig,axes=plt.subplots(1,3,figsize=(12,3.9),layout='constrained')
for ax,relative,title in zip(axes,['initial_rgb.png','rgb/0029.png','rgb/0149.png'],
                             ['Physical 2° starting tilt','Aligned above hole, 1.5 s','Inserted, 7.5 s']):
    with Image.open(sample['run']/relative) as image: ax.imshow(image)
    ax.set_title(title,fontsize=10)
    ax.axis('off')
fig.savefig(output/'angular-scene.png',dpi=160)
plt.close(fig)
if len(camera_poses)!=1: raise ValueError('Camera moved between dataset cases.')
result={'manifest_sha256':manifest_sha,'source_version_count':len(sources),'camera_pose_count':len(camera_poses),'episode_count':len(episodes),
        'successful_episodes':sum(r['task_success'] for r in records),'transition_count':len(episodes)*150,
        'verified_png_count':image_count,'results':records,
        'interpretation':'Scripted oracle expert and conversion pilot; no learned UR5 policy or generalization claim.'}
(output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
(output/'verification.log').write_text(capture.getvalue()+f'PNG_VERIFIED: {image_count}\nSOURCE_VERSION_COUNT: {len(sources)}\n')
print(json.dumps({k:v for k,v in result.items() if k!='results'},indent=2))
