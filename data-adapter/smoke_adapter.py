"""Check every TFDS episode, upstream chunks and a real OpenVLA training batch."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
import tensorflow_datasets as tfds
import torch

from adapter_core import collect_episodes,normalize,read_json
from ur5_loader import PROFILE,UR5RLDSDataset,make_ur5_dataset


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('runs',type=Path,nargs='+')
    args=parser.parse_args()
    episodes,sha=collect_episodes(args.dataset/'dataset_manifest.json',args.runs)
    by_id={e['id']:e for e in episodes}
    statistics=read_json(args.dataset/'train_statistics.json')
    before=hashlib.sha256((args.dataset/'train_statistics.json').read_bytes()).hexdigest()
    builder=tfds.builder('ur5_insertion_pilot',data_dir=str(args.dataset/'tfds'))
    observations=actions=0
    split_counts={}
    for split_tfds,split in [('train','train'),('val','validation'),('test','test')]:
        seen=set()
        for episode in tfds.as_numpy(builder.as_dataset(split=split_tfds,shuffle_files=False)):
            identifier=episode['episode_metadata']['scenario_id'].decode()
            source=by_id[identifier]
            assert source['split']==split and identifier not in seen
            seen.add(identifier)
            rows=list(episode['steps'])
            assert len(rows)==151
            assert sum(bool(r['is_first']) for r in rows)==1 and rows[0]['is_first']
            assert sum(bool(r['is_last']) for r in rows)==1 and rows[-1]['is_last']
            assert sum(bool(r['is_terminal']) for r in rows)==1 and rows[-1]['is_terminal']
            for i,row in enumerate(rows):
                assert set(row['observation'])=={'image','proprio'}
                native=source['transitions'][i]['observation'] if i<150 else source['transitions'][-1]['next_observation']
                np.testing.assert_array_equal(row['observation']['proprio'],np.asarray(native['proprio'],dtype=np.float32))
                with Image.open(source['run']/native['rgb']) as image:
                    np.testing.assert_array_equal(row['observation']['image'],np.asarray(image.convert('RGB')))
                if i<150:
                    np.testing.assert_array_equal(row['action'],np.asarray(source['transitions'][i]['action'],dtype=np.float32))
                observations+=1
                actions+=int(i<150)
        assert seen=={e['id'] for e in episodes if e['split']==split}
        split_counts[split]=len(seen)
    chunk_counts={}
    for split in ('train','validation'):
        dataset,_=make_ur5_dataset(args.dataset,split,decode_images=False,flatten=False)
        candidates={e['id']:e for e in episodes if e['split']==split}
        count=0
        seen=set()
        for trajectory in dataset.as_numpy_iterator():
            assert trajectory['action'].shape==(143,8,7)
            first=trajectory['observation']['proprio'][0,0]
            distances={identifier:np.max(np.abs(first-normalize(e['transitions'][0]['observation']['proprio'],statistics['proprio'])))
                       for identifier,e in candidates.items()}
            identifier=min(distances,key=distances.get)
            assert distances[identifier]<2e-4 and identifier not in seen
            seen.add(identifier)
            raw=np.asarray([t['action'] for t in candidates[identifier]['transitions']],dtype=np.float32)
            normalized=normalize(raw,statistics['action'])
            expected=np.stack([normalized[i:i+8] for i in range(143)])
            np.testing.assert_allclose(trajectory['action'],expected,atol=2e-5,rtol=2e-5)
            assert np.all(trajectory['action'][...,6]==0)
            count+=143
        assert seen==set(candidates)
        chunk_counts[split]=count

    # Processor/tokenizer only: the 7B model weights are not loaded or trained.
    from transformers import AutoProcessor
    from prismatic.vla.action_tokenizer import ActionTokenizer
    from prismatic.vla.datasets import RLDSBatchTransform
    from prismatic.models.backbones.llm.prompting import PurePromptBuilder
    from prismatic.util.data_utils import PaddedCollatorForActionPrediction
    from prismatic.vla.constants import ACTION_TOKEN_BEGIN_IDX,IGNORE_INDEX
    processor=AutoProcessor.from_pretrained(str(args.checkpoint),trust_remote_code=True,local_files_only=True)
    transform=RLDSBatchTransform(ActionTokenizer(processor.tokenizer),processor.tokenizer,
                                image_transform=processor.image_processor.apply_transform,
                                prompt_builder_fn=PurePromptBuilder,use_wrist_image=False,use_proprio=True)
    train=UR5RLDSDataset(args.dataset,transform,train=True)
    iterator=iter(train)
    examples=[next(iterator),next(iterator)]
    collator=PaddedCollatorForActionPrediction(processor.tokenizer.model_max_length,processor.tokenizer.pad_token_id,padding_side='right')
    batch=collator(examples)
    assert set(batch)=={'pixel_values','proprio','input_ids','attention_mask','labels','actions','dataset_names'}
    assert tuple(batch['actions'].shape)==(2,8,7)
    assert tuple(batch['proprio'].shape)==(2,8)
    assert torch.isfinite(batch['actions']).all() and torch.isfinite(batch['proprio']).all()
    assert torch.isfinite(batch['pixel_values']).all()
    action_tokens=((batch['labels']>ACTION_TOKEN_BEGIN_IDX)&(batch['labels']!=IGNORE_INDEX)).sum(-1)
    assert action_tokens.tolist()==[56,56],action_tokens.tolist()
    for labels in batch['labels']:
        active=labels[labels!=IGNORE_INDEX]
        assert len(active)==57 and int(active[-1])==processor.tokenizer.eos_token_id
        assert bool((active[:-1]>ACTION_TOKEN_BEGIN_IDX).all())
    assert len(train)==1144
    assert hashlib.sha256((args.dataset/'train_statistics.json').read_bytes()).hexdigest()==before
    def shapes(value):
        return {k:shapes(v) for k,v in value.items()} if isinstance(value,dict) else list(value.shape)
    report={'passed':True,'manifest_sha256':sha,'split_episode_counts':split_counts,
            'tfds_observations_verified_pixel_for_pixel':observations,'native_actions_verified':actions,
            'chunks_verified_against_native_actions':chunk_counts,
            'chunk_tail_policy':'Discard final 7 start indices; no chunk crosses an episode; terminal placeholder excluded.',
            'upstream_training_batch_shapes':{k:shapes(v) for k,v in batch.items() if hasattr(v,'shape') or isinstance(v,dict)},
            'supervised_action_tokens_per_example':action_tokens.tolist(),
            'statistics_unchanged_after_validation':True,'profile':PROFILE,'model_weights_loaded':False,'training_started':False}
    (args.dataset/'adapter_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('UR5_ADAPTER_VERIFIED',json.dumps(report),flush=True)


if __name__=='__main__': main()
