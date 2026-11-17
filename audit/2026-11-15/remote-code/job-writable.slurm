#!/bin/bash -l
#SBATCH --job-name=ur5-pilot
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --output=ur5-%j.log

set -euo pipefail
mode=${1:-}
case "$mode" in
    image|record|replay) shift ;;
    *) echo 'Usage: sbatch [resources] job.slurm image|record|replay [previous steps.jsonl]' >&2; exit 2 ;;
esac

: "${SLURM_JOB_ID:?Submit this script with sbatch.}"
project=${SLURM_SUBMIT_DIR:?}
cd "$project"
runtime="$project/.runtime"
mkdir -p "$runtime"
image="$runtime/isaac-lab-2.3.0-amd64.sif"
registry='docker://nvcr.io/nvidia/isaac-lab@sha256:f1eae1f847cc77e00738d919138d78dde9a12589da9a83b4909555a4abeddb20'

set +u
module load singularity/4.3.2
set -u

if [[ "$mode" == image ]]; then
    exec 9>"$runtime/image.lock"
    flock 9
    if [[ -s "$image" ]]; then
        singularity sif list "$image"
        exit 0
    fi
    export SINGULARITY_CACHEDIR="$runtime/singularity-cache"
    export SINGULARITY_TMPDIR="$runtime/singularity-tmp"
    mkdir -p "$SINGULARITY_CACHEDIR" "$SINGULARITY_TMPDIR"
    partial="$runtime/isaac-lab-$SLURM_JOB_ID.partial.sif"
    trap 'rm -f "$partial"' EXIT
    singularity pull "$partial" "$registry"
    singularity sif list "$partial"
    mv "$partial" "$image"
    exit 0
fi

if [[ ${ACCEPT_EULA:-} != Y ]]; then
    echo 'Review the NVIDIA license before exporting ACCEPT_EULA=Y and submitting the job.' >&2
    exit 1
fi
test -s "$image" || { echo 'Run the image job first.' >&2; exit 1; }
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
mkdir -p "$runtime/home" "$project/runs"
run_args=()
if [[ "$mode" == replay ]]; then
    replay_path=${1:?Pass runs/JOB_ID/steps.jsonl}
    [[ "$replay_path" =~ ^runs/[0-9]+/steps\.jsonl$ && -f "$replay_path" ]] || {
        echo 'Pass an existing runs/JOB_ID/steps.jsonl file.' >&2
        exit 2
    }
    run_args=(--replay "/pilot/$replay_path")
fi

gpu_args=()
if [[ -n ${CUDA_VISIBLE_DEVICES:-} ]]; then
    gpu_args=(--env "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES")
fi
writable="$runtime/writable-$SLURM_JOB_ID"
mkdir -p "$writable"/{cache,data,logs} "$runtime/home/Documents/Kit/shared"

singularity exec --nv --cleanenv --env ACCEPT_EULA=Y \
    --bind "$writable/cache:/isaac-sim/kit/cache" \
    --bind "$writable/data:/isaac-sim/kit/data" \
    --bind "$writable/logs:/isaac-sim/kit/logs" \
    "${gpu_args[@]}" \
    --home "$runtime/home:/root" --bind "$project:/pilot" --pwd /workspace/isaaclab \
    "$image" /workspace/isaaclab/isaaclab.sh -p /pilot/run_ur5.py \
    --headless --enable_cameras --output "/pilot/runs/$SLURM_JOB_ID" "${run_args[@]}"
