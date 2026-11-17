"""Read-only VALAR installation audit. Load git/2.9.5 and singularity/4.3.2 first."""
import argparse
from datetime import datetime,timezone
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import struct
import subprocess

ROOT=Path(__file__).resolve().parent
REVISIONS={'openvla-oft':'e4287e94541f459edc4feabc4e181f537cd569a8',
           'LIBERO':'8f1084e3132a39270c3a13ebe37270a43ece2a01',
           'transformers':'bc339d9ad707454c0c115970db43c260067c61ab',
           'dlimp':'040105d256bd28866cc6620621a3d5f7b6b91b46'}
CHECKPOINT='95220f9a3421a7ff12d4218e73d09ade830fa9a3'


def command(*arguments): return subprocess.check_output(arguments,text=True).strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'deliverables/week2/environment.json')
    args=parser.parse_args()
    runtime=ROOT/'.runtime'
    python=runtime/'env/bin/python'
    # Must be called with the project interpreter so package metadata is relevant.
    if Path(os.sys.executable).resolve()!=python.resolve():
        raise ValueError('Run with .runtime/env/bin/python on VALAR.')
    pip=command(str(python),'-m','pip','check')
    versions={name:command('git','-C',str(runtime/name),'rev-parse','HEAD') for name in REVISIONS}
    if versions!=REVISIONS: raise ValueError('Installed source revisions differ from the verified baseline.')
    image=ROOT/'ur5-pilot/.runtime/isaac-lab-2.3.0-amd64.sif'
    sif=command('singularity','sif','list',str(image))
    if 'Squashfs/*System/amd64' not in sif: raise ValueError('Unexpected Isaac container architecture.')
    model=runtime/'huggingface/hub/models--moojink--openvla-7b-oft-finetuned-libero-10'
    if (model/'refs/main').read_text().strip()!=CHECKPOINT:
        raise ValueError('Cached main revision differs from the recorded reference model.')
    snapshot=model/'snapshots'/CHECKPOINT
    index=json.loads((snapshot/'model.safetensors.index.json').read_text())
    shards=sorted(set(index['weight_map'].values()))
    shard_info={}
    for name in shards:
        path=snapshot/name
        with path.open('rb') as stream:
            length=struct.unpack('<Q',stream.read(8))[0]
            if not 0<length<16*1024*1024: raise ValueError(f'Invalid safetensors header: {name}')
            header=json.loads(stream.read(length))
        available=path.stat().st_size-8-length
        expected=[key for key,value in index['weight_map'].items() if value==name]
        if not expected or any(key not in header for key in expected): raise ValueError('Missing tensor metadata.')
        if max(v['data_offsets'][1] for k,v in header.items() if k!='__metadata__')!=available:
            raise ValueError(f'Truncated or inconsistent model shard: {name}')
        shard_info[name]={'bytes':path.stat().st_size,'indexed_tensors':len(expected)}
    for name in ['config.json','preprocessor_config.json','tokenizer.json','dataset_statistics.json',
                 'action_head--150000_checkpoint.pt','proprio_projector--150000_checkpoint.pt']:
        if not (snapshot/name).is_file() or (snapshot/name).stat().st_size==0:
            raise ValueError(f'Missing model component: {name}')
    packages={name:metadata.version(name) for name in ['torch','torchvision','transformers','numpy',
              'tensorflow','tensorflow-datasets','mujoco','robosuite','huggingface-hub']}
    queue=command('squeue','-h','-u',os.environ['USER'],'-o','%i|%j|%T|%R')
    report={'checked_at_utc':datetime.now(timezone.utc).isoformat(),'passed':True,
            'hostname':platform.node(),'python':platform.python_version(),'glibc':command('getconf','GNU_LIBC_VERSION'),
            'pip_check':pip,'source_revisions':versions,'packages':packages,
            'isaac_lab':'2.3.0','isaac_sim':'5.1.0','isaac_sif_bytes':image.stat().st_size,
            'isaac_sif_table':sif,'checkpoint_revision':CHECKPOINT,'weight_shards':shard_info,
            'model_file_check':'Index, tensor headers, data lengths and required components; no new inference.',
            'active_jobs':queue.splitlines() if queue else [],'gpu_jobs_submitted':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
