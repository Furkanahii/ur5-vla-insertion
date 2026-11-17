#!/bin/bash -l
#SBATCH --job-name=ur5-insertion
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:15:00
#SBATCH --output=insertion-%A_%a.log

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch.}"
project=${SLURM_SUBMIT_DIR:?}
cd "$project"
runtime="$project/../ur5-pilot/.runtime"
image="$runtime/isaac-lab-2.3.0-amd64.sif"
test -s "$image"
[[ ${ACCEPT_EULA:-} == Y ]] || { echo 'Set ACCEPT_EULA=Y after accepting the NVIDIA license.' >&2; exit 1; }
scenario=${1:-aligned}
offset_x=0
offset_y=0
dataset_args=()
if [[ "$scenario" == dataset ]]; then
    index=${SLURM_ARRAY_TASK_ID:-${2:-}}
    [[ "$index" =~ ^[0-9]+$ ]] || { echo 'Use --array=0-11%1 or dataset INDEX.' >&2; exit 2; }
    identifier=$("$project/../.runtime/env/bin/python" -c 'import sys; from dataset_manifest import load_manifest; m,_=load_manifest("pilot_manifest.json"); print(m["cases"][int(sys.argv[1])]["id"])' "$index")
    dataset_args=(--manifest /task-code/pilot_manifest.json --scenario-id "$identifier")
    scenario=aligned
fi
if [[ "$scenario" == validation ]]; then
    case ${SLURM_ARRAY_TASK_ID:-} in
        0) scenario=aligned ;;
        1) scenario=rim ;;
        2) scenario=filled ;;
        *) echo 'Use --array=0-2%1.' >&2; exit 2 ;;
    esac
fi
if [[ "$scenario" == demonstrations ]]; then
    case ${SLURM_ARRAY_TASK_ID:-} in
        0) offset_x=3 ;;
        1) offset_x=-3 ;;
        2) offset_y=3 ;;
        3) offset_y=-3 ;;
        *) echo 'Use --array=0-3%1.' >&2; exit 2 ;;
    esac
    scenario=aligned
fi
case "$scenario" in aligned|rim|filled) ;; *) exit 2 ;; esac
run_id="${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}${SLURM_ARRAY_TASK_ID:+_$SLURM_ARRAY_TASK_ID}"
run="$project/runs/$run_id"
code_dir="$runtime/insertion-code-$run_id"
writable="$runtime/insertion-$run_id"
mkdir -p "$run" "$code_dir" "$writable"/{data,logs} "$runtime/kit-cache" "$runtime/home/Documents/Kit/shared"
cp "$project/"{run_insertion.py,scene_geometry.py,task_math.py,check_insertion.py,dataset_manifest.py,pilot_manifest.json} "$code_dir/"
cp "$project/../ur5-pilot/episode.py" "$code_dir/"
(cd "$code_dir" && sha256sum *.py *.json) > "$run/source.sha256"
printf '%s\n' 'docker://nvcr.io/nvidia/isaac-lab@sha256:f1eae1f847cc77e00738d919138d78dde9a12589da9a83b4909555a4abeddb20' > "$run/container.txt"
set +u
module load singularity/4.3.2
set -u
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv | tee "$run/gpu.csv"
exec 8>"$runtime/kit-cache.lock"
flock 8
gpu_args=()
if [[ -n ${CUDA_VISIBLE_DEVICES:-} ]]; then gpu_args=(--env "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"); fi
timeout --signal=TERM --kill-after=30s 12m \
    singularity exec --nv --cleanenv --env ACCEPT_EULA=Y --env TERM=xterm --env PYTHONUNBUFFERED=1 \
    "${gpu_args[@]}" --home "$runtime/home:/root" \
    --bind "$runtime/kit-cache:/isaac-sim/kit/cache" --bind "$writable/data:/isaac-sim/kit/data" \
    --bind "$writable/logs:/isaac-sim/kit/logs" --bind "$project:/task" --bind "$code_dir:/task-code:ro" \
    --pwd /workspace/isaaclab "$image" /workspace/isaaclab/isaaclab.sh -p /task-code/run_insertion.py \
    --headless --enable_cameras --scenario "$scenario" --offset-x-mm "$offset_x" --offset-y-mm "$offset_y" \
    "${dataset_args[@]}" --output "/task/runs/$run_id"
"$project/../.runtime/env/bin/python" "$code_dir/check_insertion.py" "$run"
