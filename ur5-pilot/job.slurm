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
    image|record|replay|diagnose) shift ;;
    *) echo 'Usage: sbatch [resources] job.slurm image|record|replay|diagnose [arguments]' >&2; exit 2 ;;
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
run_id="$SLURM_JOB_ID"
if [[ "$mode" == replay ]]; then
    replay_path=${1:?Pass runs/JOB_ID/steps.jsonl}
    [[ "$replay_path" =~ ^runs/[0-9]+(_[0-9]+)?/steps\.jsonl$ && -f "$replay_path" ]] || {
        echo 'Pass an existing runs/JOB_ID/steps.jsonl file.' >&2
        exit 2
    }
    run_args=(--replay "/pilot/$replay_path")
    shift
elif [[ "$mode" == diagnose ]]; then
    (( $# == 0 )) || { echo 'Diagnostic array accepts no extra arguments.' >&2; exit 2; }
    case ${SLURM_ARRAY_TASK_ID:-} in
        0|1) motion=joint-hold ;;
        2|3) motion=hold ;;
        4|5) motion=x ;;
        *) echo 'Use --array=0-5%1 for the six matched diagnostics.' >&2; exit 2 ;;
    esac
    run_id="${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
    run_args=(--motion "$motion")
    if (( SLURM_ARRAY_TASK_ID % 2 == 1 )); then run_args+=(--disable-gravity); fi
fi
# Only expose bounded pilot parameters, keeping output paths managed by Slurm.
while (( $# )); do
    case "$1" in
        --disable-gravity|--gravity-compensation|--replay-actions) run_args+=("$1"); shift ;;
        --motion|--warmup-steps|--dx-m)
            [[ "$mode" != diagnose && $# -ge 2 ]] || { echo 'Invalid pilot arguments.' >&2; exit 2; }
            run_args+=("$1" "$2"); shift 2 ;;
        *) echo "Unknown pilot argument: $1" >&2; exit 2 ;;
    esac
done

gpu_args=()
if [[ -n ${CUDA_VISIBLE_DEVICES:-} ]]; then
    gpu_args=(--env "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES")
fi
run="$project/runs/$run_id"
writable="$runtime/writable-$run_id"
code_dir="$runtime/code-$run_id"
cache="$runtime/kit-cache"
mkdir -p "$run" "$code_dir" "$cache" "$writable"/{data,logs} "$runtime/home/Documents/Kit/shared"
# Reuse compiled shaders between runs. Keep one process in the shared Kit cache.
exec 8>"$runtime/kit-cache.lock"
flock 8
cp "$project/"{run_ur5.py,motion.py,diagnostics.py,episode.py,check_pilot.py} "$code_dir/"
(cd "$code_dir" && sha256sum *.py) > "$run/source.sha256"
printf '%s\n' "$registry" > "$run/container.txt"
export PYTHONUNBUFFERED=1
timeout --signal=TERM --kill-after=30s 12m \
    singularity exec --nv --cleanenv --env ACCEPT_EULA=Y --env PYTHONUNBUFFERED=1 --env TERM=xterm \
    --bind "$cache:/isaac-sim/kit/cache" \
    --bind "$writable/data:/isaac-sim/kit/data" \
    --bind "$writable/logs:/isaac-sim/kit/logs" \
    "${gpu_args[@]}" \
    --home "$runtime/home:/root" --bind "$project:/pilot" --bind "$code_dir:/pilot-code:ro" --pwd /workspace/isaaclab \
    "$image" /workspace/isaaclab/isaaclab.sh -p /pilot-code/run_ur5.py \
    --headless --enable_cameras --output "/pilot/runs/$run_id" "${run_args[@]}"
# SimulationApp fast shutdown can replace a raised exception's process status.
# Check the saved result independently, outside the simulator process.
"$project/../.runtime/env/bin/python" "$code_dir/check_pilot.py" "$run"
