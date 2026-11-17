"""Build the complete frozen pilot and save training-only normalization stats."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from adapter_core import clipping_report,collect_episodes,fit_statistics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('runs',type=Path,nargs='+')
    args=parser.parse_args()
    episodes,sha=collect_episodes(args.manifest,args.runs)
    statistics=fit_statistics(episodes,sha)
    args.output.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(args.manifest,args.output/'dataset_manifest.json')
    def save(name,data):
        (args.output/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    save('train_statistics.json',statistics)
    save('clipping_report.json',clipping_report(episodes,statistics))
    save('source_episodes.json',[{'scenario_id':e['id'],'split':e['split'],'run_id':e['run'].name,
                                'transitions_sha256':e['transitions_sha256']} for e in episodes])
    from ur5_tfds import Ur5InsertionPilot
    builder=Ur5InsertionPilot(data_dir=str(args.output/'tfds'),episodes=episodes)
    builder.download_and_prepare()
    counts={split:info.num_examples for split,info in builder.info.splits.items()}
    if counts!={'train':8,'val':2,'test':2}: raise ValueError(f'Unexpected split counts: {counts}')
    save('build_summary.json',{'dataset_name':builder.name,'version':str(builder.version),
                             'split_episode_counts':counts,'manifest_sha256':sha,
                             'normalization_fitted_episodes':statistics['num_trajectories'],
                             'normalization_fitted_transitions':statistics['num_transitions'],
                             'train_statistics_sha256':hashlib.sha256((args.output/'train_statistics.json').read_bytes()).hexdigest(),
                             'terminal_observation_included':True,
                             'model_feature_keys':['observation/image','observation/proprio','language_instruction','action']})
    print('UR5_TFDS_BUILT',json.dumps(counts),flush=True)


if __name__=='__main__': main()
