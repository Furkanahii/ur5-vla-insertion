"""RLDS/TFDS representation of the frozen, successful UR5 expert pilot."""
import numpy as np
import tensorflow_datasets as tfds


class Ur5InsertionPilot(tfds.core.GeneratorBasedBuilder):
    VERSION=tfds.core.Version('1.0.0')
    RELEASE_NOTES={'1.0.0':'UR5 RGB, 8D proprio and 7D Cartesian deltas, with terminal observations.'}

    def __init__(self,*args,episodes=None,**kwargs):
        self.episodes=episodes
        super().__init__(*args,**kwargs)

    def _info(self):
        return self.dataset_info_from_configs(
            description='12-case UR5 rigid insertion conversion pilot, not a statistical benchmark.',
            features=tfds.features.FeaturesDict({
                'episode_metadata':{'scenario_id':tfds.features.Text(),'transitions_sha256':tfds.features.Text()},
                'steps':tfds.features.Dataset({
                    'observation':{'image':tfds.features.Image(shape=(480,640,3),encoding_format='png'),
                                   'proprio':tfds.features.Tensor(shape=(8,),dtype=np.float32)},
                    'action':tfds.features.Tensor(shape=(7,),dtype=np.float32),
                    'language_instruction':tfds.features.Text(),
                    'reward':np.float32,'discount':np.float32,
                    'is_first':np.bool_,'is_last':np.bool_,'is_terminal':np.bool_,
                }),
            }),
            homepage='https://github.com/moojink/openvla-oft',
        )

    def _split_generators(self,dl_manager):
        if self.episodes is None: raise ValueError('Validated source episodes are required when building.')
        return {name:self._generate_examples(split) for name,split in
                [('train','train'),('val','validation'),('test','test')]}

    def _generate_examples(self,split):
        for episode in self.episodes:
            if episode['split']!=split: continue
            steps=[]
            for i,transition in enumerate(episode['transitions']):
                obs=transition['observation']
                steps.append({'observation':{'image':str(episode['run']/obs['rgb']),
                                             'proprio':np.asarray(obs['proprio'],dtype=np.float32)},
                              'action':np.asarray(transition['action'],dtype=np.float32),
                              'language_instruction':episode['metadata']['language_instruction'],
                              'reward':np.float32(0),'discount':np.float32(1),
                              'is_first':i==0,'is_last':False,'is_terminal':False})
            # RLDS terminal observation has no valid action. The loader explicitly
            # drops this row before chunking, so its placeholder is never a label.
            final=episode['transitions'][-1]['next_observation']
            steps.append({'observation':{'image':str(episode['run']/final['rgb']),
                                         'proprio':np.asarray(final['proprio'],dtype=np.float32)},
                          'action':np.zeros(7,dtype=np.float32),
                          'language_instruction':episode['metadata']['language_instruction'],
                          'reward':np.float32(1),'discount':np.float32(0),
                          'is_first':False,'is_last':True,'is_terminal':True})
            yield episode['id'],{'episode_metadata':{'scenario_id':episode['id'],
                                 'transitions_sha256':episode['transitions_sha256']},'steps':steps}
