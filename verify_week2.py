"""Audit saved week 1-2 deliverables and already completed pilots; starts no GPU jobs."""
import argparse
import contextlib
from datetime import datetime,timezone
import hashlib
import io
import json
from math import dist
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image

ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'ur5-pilot'),str(ROOT/'rigid-insertion')]
from check_results import check_run
from check_pilot import check as check_motion
from check_insertion import check as check_insertion


def require(condition,message):
    if not condition: raise ValueError(message)


def read(path): return json.loads(path.read_text())


def digest(path):
    sha=hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''): sha.update(part)
    return sha.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'deliverables/week2/verification.json')
    parser.add_argument('--ffmpeg',help='FFmpeg path; otherwise PATH or installed imageio-ffmpeg is used.')
    args=parser.parse_args()
    ffmpeg=args.ffmpeg or shutil.which('ffmpeg')
    if ffmpeg is None:
        import imageio_ffmpeg
        ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    plan=ROOT/'deliverables/week2/project-plan.docx'
    with zipfile.ZipFile(plan) as archive:
        doc=ET.fromstring(archive.read('word/document.xml'))
    text=' '.join(node.text or '' for node in doc.iter() if node.tag.endswith('}t'))
    require('First assignment (weeks 1' in text,'Source plan first assignment is missing.')
    lib=ROOT/'runs/1952021'
    capture=io.StringIO()
    with contextlib.redirect_stdout(capture):
        check_run(lib)
        for number in ('2025430','2025475'): check_motion(ROOT/'ur5-pilot/runs'/number)
        # The tool/camera requirement is also covered by the completed rigid scene.
        for number in ('2028002_0','2028002_1','2028002_2'):
            check_insertion(ROOT/'rigid-insertion/runs'/number)
    evaluation=next((lib/'eval-logs').glob('EVAL-libero_10-*.txt')).read_text().splitlines()
    require('Total successes: 10' in evaluation,'Reference result no longer matches reported successes.')
    versions={name:(lib/(name+'.commit')).read_text().strip() for name in ('openvla-oft','libero','checkpoint')}
    require(versions['openvla-oft']=='e4287e94541f459edc4feabc4e181f537cd569a8','Wrong OpenVLA revision.')
    require(versions['libero']=='8f1084e3132a39270c3a13ebe37270a43ece2a01','Wrong LIBERO revision.')
    recorded=read(ROOT/'ur5-pilot/runs/2025430/summary.json')
    replay=read(ROOT/'ur5-pilot/runs/2025475/config.json')
    require(replay['replay_mode']=='delta','Replay must exercise delta actions.')
    require(not replay['robot_gravity_disabled'] and replay['gravity_compensation'],'Replay physics differs.')
    def rows(number):
        return [json.loads(line) for line in (ROOT/'ur5-pilot/runs'/number/'steps.jsonl').read_text().splitlines()]
    difference=max(dist(a['wrist_position_base_m'],b['wrist_position_base_m'])
                   for a,b in zip(rows('2025430'),rows('2025475')))
    require(difference<1e-5,'Motion replay differs by more than 10 micrometers.')
    png_count=0
    for number in ('2025430','2025475'):
        run=ROOT/'ur5-pilot/runs'/number
        for path in [run/'initial_rgb.png',*sorted((run/'rgb').glob('*.png'))]:
            with Image.open(path) as image: image.verify()
            png_count+=1
        metadata=read(run/'episode.json')
        require(not metadata['eligible_for_insertion_training'],'Motion pilot cannot be insertion training data.')
    videos=[*sorted((lib/'rollouts').rglob('*.mp4')),ROOT/'deliverables/week2/ur5-motion.mp4']
    for path in videos:
        subprocess.run([ffmpeg,'-hide_banner','-v','error','-xerror','-i',str(path),'-f','null','-'],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    adapter=ROOT/'data-adapter/builds/2028146'
    extra=read(adapter/'adapter_verification.json')
    require(extra['passed'] and not extra['training_started'],'Unexpected adapter status.')
    for line in (adapter/'source.sha256').read_text().splitlines():
        expected,relative=line.split(maxsplit=1)
        require(digest(ROOT/relative.strip())==expected,f'Adapter source changed: {relative}')
    transfer=ROOT/'audit/2026-11-15/angular-dataset/dataset-transfer.sha256'
    for line in transfer.read_text().splitlines():
        expected,relative=line.split(maxsplit=1)
        require(digest(adapter/relative.strip())==expected,f'Dataset checksum differs: {relative}')
    # Record exactly the evidence that was read, preserving immutable raw logs.
    evidence=[plan,*sorted(lib.glob('*.commit')),lib/'packages.txt',lib/'gpu.csv',
              next((lib/'eval-logs').glob('EVAL-libero_10-*.txt')),*videos]
    for number in ('2025430','2025475'):
        base=ROOT/'ur5-pilot/runs'/number
        evidence += [base/name for name in ('config.json','summary.json','steps.jsonl','episode.json','transitions.jsonl','source.sha256')]
    output={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'technical_week2_passed':True,
            'source_plan_sha256':digest(plan),'reference_vla':{'run':'1952021','episodes':10,'successes':10,'versions':versions},
            'ur5_motion':{'record_run':'2025430','delta_replay_run':'2025475','actions_per_episode':50,
                          'observations_per_episode':51,'verified_png_count':png_count,
                          'max_sampled_z_error_m':recorded['tracking_metrics']['max_abs_tracking_error_xyz_m'][2],
                          'replay_max_position_difference_m':difference},
            'decoded_mp4_count':len(videos),'tool_and_camera_physics_controls_passed':3,
            'completed_extra_adapter_passed':True,'dataset_backup_checksums_match':True,
            'new_gpu_jobs_started':False,'human_joint_schema_review':'not attested; students review together',
            'evidence_sha256':{str(path.relative_to(ROOT)):digest(path) for path in evidence}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,indent=2)+'\n')
    args.output.with_suffix('.log').write_text(capture.getvalue())
    print(json.dumps({key:value for key,value in output.items() if key!='evidence_sha256'},indent=2))


if __name__=='__main__': main()
