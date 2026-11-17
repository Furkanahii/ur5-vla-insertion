"""Explicit UR5 loader for pinned OpenVLA-OFT; never infer LIBERO robot semantics.

Uses upstream RLDS normalization, trajectory chunking and frame transforms,
with our supplied training-only statistics. No vendor files are modified.
"""
from pathlib import Path

import tensorflow as tf
from torch.utils.data import IterableDataset

from adapter_core import read_json
from dataset_manifest import load_manifest
from ur5_tfds import Ur5InsertionPilot
from prismatic.vla.constants import ACTION_DIM,NUM_ACTIONS_CHUNK,PROPRIO_DIM,NormalizationType
from prismatic.vla.datasets.rlds.dataset import make_dataset_from_rlds,apply_trajectory_transforms,apply_frame_transforms

OFT_COMMIT='e4287e94541f459edc4feabc4e181f537cd569a8'
PROFILE={'task':'ur5_rigid_peg_insertion_v2','action_dim':7,'proprio_dim':8,'action_chunk_length':8,
         'normalization':'bounds_q99','num_images_in_input':1,'use_proprio':True,
         'action_convention':'base-frame translation and left-multiplied rotation vector deltas; fixed tool command zero'}


def remove_terminal_observation(traj):
    tf.debugging.assert_equal(traj['is_terminal'][-1],True)
    tf.debugging.assert_equal(tf.reduce_any(traj['is_terminal'][:-1]),False)
    return {'observation':tf.nest.map_structure(lambda x:x[:-1],traj['observation']),
            'action':traj['action'][:-1],'language_instruction':traj['language_instruction'][:-1]}


def make_ur5_dataset(root,split,decode_images=True,flatten=True):
    root=Path(root)
    if split not in ('train','validation','test'): raise ValueError('Unknown split.')
    if (ACTION_DIM,PROPRIO_DIM,NUM_ACTIONS_CHUNK)!=(7,8,8):
        raise ValueError('OpenVLA constants do not match the explicitly specified UR5 profile.')
    manifest,sha=load_manifest(root/'dataset_manifest.json')
    stats=read_json(root/'train_statistics.json')
    summary=read_json(root/'build_summary.json')
    import hashlib
    if hashlib.sha256((root/'train_statistics.json').read_bytes()).hexdigest()!=summary['train_statistics_sha256']:
        raise ValueError('Normalization file changed after dataset build.')
    expected=[case['id'] for case in manifest['cases'] if case['split']=='train']
    if stats['provenance']['manifest_sha256']!=sha or stats['provenance']['scenario_ids']!=expected:
        raise ValueError('Normalization must be fitted only on the frozen training cases.')
    kwargs=dict(name=Ur5InsertionPilot.name,data_dir=str(root/'tfds'),train=split=='train',shuffle=False,
                standardize_fn=remove_terminal_observation,image_obs_keys={'primary':'image'},
                state_obs_keys=['proprio'],language_key='language_instruction',
                action_proprio_normalization_type=NormalizationType.BOUNDS_Q99,
                dataset_statistics={key:stats[key] for key in ('action','proprio','num_transitions','num_trajectories')},
                absolute_action_mask=[False]*7,action_normalization_mask=[True]*6+[False],
                num_parallel_reads=1,num_parallel_calls=1)
    if split=='test':
        # Upstream's public boolean selects only train/val. Keep test completely
        # out of that API rather than silently treating validation as test.
        raise ValueError('Test is reserved for closed-loop evaluation; use validation for loader smoke checks.')
    dataset,metadata=make_dataset_from_rlds(**kwargs)
    dataset=apply_trajectory_transforms(dataset,train=split=='train',window_size=1,
                                      future_action_window_size=7,skip_unlabeled=True,num_parallel_calls=1)
    if not flatten:
        if decode_images: raise ValueError('Image decoding follows flatten(); set decode_images=False for trajectory checks.')
        return dataset,metadata
    dataset=dataset.flatten(num_parallel_calls=1)
    if decode_images:
        dataset=apply_frame_transforms(dataset,train=False,resize_size=(224,224),num_parallel_calls=1)
    return dataset,metadata


class UR5RLDSDataset(IterableDataset):
    """PyTorch adapter with the same sample contract as upstream RLDSDataset.

    The fine-tuning entry point still needs to select this class explicitly.
    A ready data loader is not a claim that a trained UR5 policy exists.
    """
    def __init__(self,root,batch_transform,train=True,seed=17,shuffle_buffer_size=256):
        self.root=Path(root)
        self.batch_transform=batch_transform
        self.split='train' if train else 'validation'
        self.dataset,stats=make_ur5_dataset(root,self.split)
        self.dataset_statistics={'ur5_insertion_pilot':stats}
        split_tfds='train' if train else 'val'
        self.dataset_length=read_json(self.root/'build_summary.json')['split_episode_counts'][split_tfds]*143
        if train:
            self.dataset=self.dataset.shuffle(shuffle_buffer_size,seed=seed,reshuffle_each_iteration=True).repeat()

    def __iter__(self):
        for batch in self.dataset.as_numpy_iterator(): yield self.batch_transform(batch)

    def __len__(self): return self.dataset_length
