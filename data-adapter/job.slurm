#!/bin/bash -l
#SBATCH --job-name=ur5-data
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:15:00
#SBATCH --output=data-%j.log
set -euo pipefail
project=${SLURM_SUBMIT_DIR:?}
cd "$project"
root="$project/.."
runtime="$root/.runtime"
python="$runtime/env/bin/python"
: "${SLURM_JOB_ID:?Submit with sbatch.}"
array=${1:?Provide the completed insertion array ID.}
[[ "$array" =~ ^[0-9]+$ ]] || exit 2
code="$runtime/data-code-$SLURM_JOB_ID"
mkdir -p "$code/"{data-adapter,rigid-insertion,ur5-pilot}
cp "$project/"*.py "$code/data-adapter/"
cp "$root/rigid-insertion/"{task_math.py,dataset_manifest.py,check_insertion.py,pilot_manifest.json} "$code/rigid-insertion/"
cp "$root/ur5-pilot/episode.py" "$code/ur5-pilot/"
export PYTHONPATH="$code/data-adapter:$runtime/openvla-oft"
export HF_HOME="$runtime/huggingface"
export HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false TF_CPP_MIN_LOG_LEVEL=2
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export TF_NUM_INTRAOP_THREADS=2 TF_NUM_INTEROP_THREADS=2
export CUDA_VISIBLE_DEVICES=""
export PYTHONUNBUFFERED=1
set +u
module load git/2.9.5
set -u
actual=$(git -C "$runtime/openvla-oft" rev-parse HEAD)
[[ "$actual" == e4287e94541f459edc4feabc4e181f537cd569a8 ]] || { echo 'Unexpected OFT version.' >&2; exit 1; }
cd "$code/data-adapter"
output="$project/builds/$SLURM_JOB_ID"
runs=()
for index in {0..11}; do runs+=("$root/rigid-insertion/runs/${array}_$index"); done
"$python" -m unittest discover -s "$code/data-adapter" -p 'test_*.py' -v
"$python" "$code/data-adapter/build_dataset.py" --manifest "$code/rigid-insertion/pilot_manifest.json" --output "$output" "${runs[@]}"
(cd "$code" && find . -type f -name '*.py' -print0 | sort -z | xargs -0 sha256sum) > "$output/source.sha256"
printf '%s\n' "$actual" > "$output/openvla.commit"
checkpoint_ref="$HF_HOME/hub/models--moojink--openvla-7b-oft-finetuned-libero-10/refs/main"
checkpoint="$HF_HOME/hub/models--moojink--openvla-7b-oft-finetuned-libero-10/snapshots/$(cat "$checkpoint_ref")"
"$python" "$code/data-adapter/smoke_adapter.py" --dataset "$output" --checkpoint "$checkpoint" "${runs[@]}"
