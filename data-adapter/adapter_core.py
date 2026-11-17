"""Validated episode selection and training-only OpenVLA normalization."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'rigid-insertion'),str(ROOT/'ur5-pilot')]
from check_insertion import check
from dataset_manifest import get_case,load_manifest,verify_run_case
from episode import model_inputs

ACTION_FLOOR=np.array([1e-4]*3+[1e-3]*3+[1.0])
PROPRIO_FLOOR=np.array([1e-3]*3+[1e-2]*3+[1.0]*2)


def read_json(path): return json.loads(Path(path).read_text())


def collect_episodes(manifest_path,runs):
    manifest,sha=load_manifest(manifest_path)
    found={}
    for path in map(Path,runs):
        config,metadata=read_json(path/'config.json'),read_json(path/'episode.json')
        case=verify_run_case(path,config,metadata)
        if metadata['manifest_sha256']!=sha or get_case(manifest,case['id'])!=case:
            raise ValueError('Mixed manifest versions are forbidden.')
        if case['id'] in found: raise ValueError('Repeated case ID: choose exactly one run per scenario.')
        check(path)
        transitions=[json.loads(line) for line in (path/'transitions.jsonl').read_text().splitlines()]
        # Only the explicit whitelist can enter model features.
        inputs=[model_inputs(t,metadata['language_instruction']) for t in transitions]
        if any(set(x)!={'image_path','proprio','language_instruction'} for x in inputs):
            raise ValueError('Unexpected model input fields.')
        found[case['id']]={'id':case['id'],'split':case['split'],'run':path,
                          'metadata':metadata,'transitions':transitions,
                          'transitions_sha256':hashlib.sha256((path/'transitions.jsonl').read_bytes()).hexdigest()}
    if set(found)!={case['id'] for case in manifest['cases']}:
        raise ValueError('Dataset must contain every frozen case exactly once.')
    return [found[case['id']] for case in manifest['cases']],sha


def moments(values,floor,mask):
    values=np.asarray(values,dtype=np.float64)
    if values.ndim!=2 or values.shape[1]!=len(floor) or not np.isfinite(values).all():
        raise ValueError('Invalid training vectors.')
    low,high=np.quantile(values,[.01,.99],axis=0)
    # Prevent numerical simulation noise in almost-constant axes from being
    # amplified into large targets. Preserve the raw percentiles for audit.
    center=(high+low)/2
    span=np.maximum(high-low,floor)
    return {'mean':values.mean(0).tolist(),'std':values.std(0).tolist(),
            'min':values.min(0).tolist(),'max':values.max(0).tolist(),
            'q01':(center-span/2).tolist(),'q99':(center+span/2).tolist(),
            'raw_q01':low.tolist(),'raw_q99':high.tolist(),
            'minimum_normalization_span':floor.tolist(),'mask':list(mask)}


def fit_statistics(episodes,manifest_sha):
    train=[e for e in episodes if e['split']=='train']
    if not train: raise ValueError('No training episodes.')
    actions=[t['action'] for e in train for t in e['transitions']]
    proprio=[t['observation']['proprio'] for e in train for t in e['transitions']]
    return {'action':moments(actions,ACTION_FLOOR,[True]*6+[False]),
            'proprio':moments(proprio,PROPRIO_FLOOR,[True]*6+[False]*2),
            'num_transitions':len(actions),'num_trajectories':len(train),
            'provenance':{'fit_split':'train','manifest_sha256':manifest_sha,
                          'scenario_ids':[e['id'] for e in train],
                          'transition_hashes':{e['id']:e.get('transitions_sha256') for e in train},
                          'method':'BOUNDS_Q99 with recorded minimum spans; fixed tool dimensions remain zero'}}


def normalize(values,stats):
    x=np.asarray(values,dtype=np.float64)
    low,high=np.array(stats['q01']),np.array(stats['q99'])
    normalized=np.clip(2*(x-low)/(high-low+1e-8)-1,-1,1)
    out=np.where(np.array(stats['mask']),normalized,x)
    return np.where(np.array(stats['min'])==np.array(stats['max']),0.0,out)


def clipping_report(episodes,stats):
    report={}
    for split in ('train','validation','test'):
        selected=[e for e in episodes if e['split']==split]
        record={'episodes':len(selected)}
        for key,getter in [('action',lambda t:t['action']),('proprio',lambda t:t['observation']['proprio'])]:
            values=np.asarray([getter(t) for e in selected for t in e['transitions']])
            low,high=np.array(stats[key]['q01']),np.array(stats[key]['q99'])
            outside=((values<low)|(values>high))&np.array(stats[key]['mask'])
            record[key+'_outside_bounds_per_dimension']=outside.sum(0).tolist()
            record['transitions']=len(values)
        report[split]=record
    return report
