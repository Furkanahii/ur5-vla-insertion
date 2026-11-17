"""Verify recorded USD-task results and generate measured-data figures."""
from pathlib import Path
from math import dist
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

output=Path(__file__).resolve().parent
project=output.parents[2]
sys.path[:0]=[str(project/'rigid-insertion'),str(project/'ur5-pilot')]
from check_insertion import check
from episode import model_inputs

base=project/'rigid-insertion'/'runs'
run_ids=[f'2025864_{i}' for i in range(3)]+[f'2025865_{i}' for i in range(4)]
reports=[]
records={}
source_versions=set()
image_count=0
for run_id in run_ids:
    root=base/run_id
    check(root)
    summary=json.loads((root/'summary.json').read_text())
    config=json.loads((root/'config.json').read_text())
    transitions=[json.loads(line) for line in (root/'transitions.jsonl').read_text().splitlines()]
    records[run_id]=transitions
    vectors=[row['observation']['proprio'][3:6] for row in transitions]
    max_jump=max(dist(a,b) for a,b in zip(vectors,vectors[1:]))
    for row in transitions:
        assert set(model_inputs(row,'Insert the peg into the hole.'))=={'image_path','proprio','language_instruction'}
    source_versions.add((root/'source.sha256').read_text())
    files=[root/'initial_rgb.png']+sorted((root/'rgb').glob('*.png'))
    assert len(files)==151
    for file in files:
        with Image.open(file) as image:
            assert image.size==(640,480)
            image.verify()
        image_count+=1
    reports.append({'run':run_id,'task_id':config['task_id'],'scenario':summary['scenario'],
                    'fixture_offset_xy_mm':[v*1000 for v in config['geometry']['fixture_offset_xy_m']],
                    'task_success':summary['task_success'],'validation_passed':summary['validation_passed'],
                    'final_depth_mm':summary['final_metrics']['depth_m']*1000,
                    'max_depth_mm':summary['max_insertion_depth_m']*1000,
                    'final_lateral_error_mm':summary['final_metrics']['tip_lateral_error_m']*1000,
                    'final_axis_tilt_deg':summary['final_metrics']['axis_tilt_deg'],
                    'contact_steps':summary['contact_control_steps'],
                    'peak_normal_force_n_raw_unvalidated':summary['peak_contact_normal_force_n_raw'],
                    'max_adjacent_proprio_rotation_jump_rad':max_jump})
result={'runs':reports,'verified_png_count':image_count,'transition_count':1050,
        'source_version_count':len(source_versions),'physics_controls_passed':sum(row['validation_passed'] for row in reports[:3]),
        'offset_demonstrations_succeeded':sum(row['task_success'] for row in reports[3:]),
        'learned_policy_used':False,'contact_wrench_validated':False,
        'scope':'One geometry/camera, four fixed lateral offsets, zero initial angular offsets. Not a statistical VLA benchmark.'}
(output/'results.json').write_text(json.dumps(result,indent=2)+'\n')

fig,axes=plt.subplots(2,1,figsize=(9,7),sharex=True,constrained_layout=True)
labels=['Hizalı — yerleşti','Kenar — engellendi','Kapak — engellendi']
for run_id,label,style in zip(run_ids[:3],labels,['-','--',':']):
    rows=records[run_id]
    axes[0].plot([r['next_observation']['time_s'] for r in rows],
                 [1000*r['evaluation']['insertion']['depth_m'] for r in rows],label=label,linestyle=style,linewidth=2)
axes[0].axhline(18,color='#8b9198',linewidth=1,linestyle='--',label='Asgari başarı derinliği')
axes[0].set_ylabel('Ölçülen giriş derinliği (mm)')
axes[0].legend(fontsize=9)
for report in reports[3:]:
    rows=records[report['run']]
    xy=report['fixture_offset_xy_mm']
    label=f'Delik ofseti: X={xy[0]:g}, Y={xy[1]:g} mm'
    times=[row['observation']['time_s'] for row in rows]
    lateral=[]
    for row in rows:
        position=row['observation']['tcp_position_base_m']
        hole=row['evaluation']['hole_top_world_m']
        lateral.append(1000*dist(position[:2],hole[:2]))
    axes[1].plot(times,lateral,label=label,linewidth=1.8)
axes[1].set_ylabel('Pim ucunun yanal uzaklığı (mm)')
axes[1].set_xlabel('Simülasyon süresi (s)')
axes[1].legend(fontsize=9)
for axis in axes: axis.grid(alpha=.2)
fig.suptitle('UR5 rijit yerleştirme — betikli uzman ve fizik kontrolleri')
fig.savefig(output/'validation.png',dpi=160)

fig,axes=plt.subplots(1,3,figsize=(15,4.5),constrained_layout=True)
for axis,run_id,label in zip(axes,run_ids[:3],labels):
    with Image.open(base/run_id/'rgb/0149.png') as image: axis.imshow(image)
    axis.set_title(label,fontsize=13)
    axis.axis('off')
fig.savefig(output/'scene-comparison.png',dpi=150)
print(json.dumps(result,indent=2))
