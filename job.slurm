#!/bin/bash -l
#SBATCH --job-name=vla-libero
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=slurm-%x-%j.out

set -euo pipefail

mode=${1:-}
case "$mode" in
    setup|wheels|model|prepare|smoke|eval) ;;
    *) echo 'Kullanım: sbatch [kaynak seçenekleri] job.slurm setup|wheels|model|prepare|smoke|eval' >&2; exit 2 ;;
esac
: "${SLURM_JOB_ID:?Bu betiği Slurm üzerinden sbatch ile çalıştırın.}"
project=${SLURM_SUBMIT_DIR:?}
cd "$project"

runtime="$project/.runtime"
environment="$runtime/env"
python="$environment/bin/python"
oft="$runtime/openvla-oft"
libero="$runtime/LIBERO"
mkdir -p "$runtime"
export HF_HOME="$runtime/huggingface"
export HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export HF_HUB_DOWNLOAD_TIMEOUT=60
export PIP_CACHE_DIR="$runtime/pip-cache"
export CONDA_PKGS_DIRS="$runtime/conda-pkgs"
export LIBERO_CONFIG_PATH="$runtime/libero-config"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export TF_FORCE_GPU_ALLOW_GROWTH=true
export WANDB_MODE=disabled
export PYTHONUNBUFFERED=1

checkpoint=moojink/openvla-7b-oft-finetuned-libero-10
fetch_checkpoint() {
    "$python" - "$checkpoint" <<'PY'
import sys

from huggingface_hub import snapshot_download

checkpoint = snapshot_download(sys.argv[1], max_workers=4, ignore_patterns=['lora_adapter/*'])
print(f'Checkpoint ready: {checkpoint}')
PY
}

if [[ "$mode" == model ]]; then
    hub_client="$runtime/hub-client"
    "$python" -m pip install --index-url https://pypi.org/simple --target "$hub_client" \
        'huggingface-hub==0.34.4'
    PYTHONPATH="$hub_client${PYTHONPATH:+:$PYTHONPATH}" fetch_checkpoint
    exit 0
fi

if [[ "$mode" == wheels ]]; then
    mkdir -p "$runtime/wheelhouse"
    # These are the Linux CUDA dependencies of the pinned PyTorch 2.2.0 wheel.
    xargs -P 4 -n 1 "$python" -m pip download --index-url https://pypi.org/simple \
        --no-deps --only-binary=:all: --dest "$runtime/wheelhouse" <<'PACKAGES'
nvidia-cudnn-cu12==8.9.2.26
nvidia-cublas-cu12==12.1.3.1
nvidia-cusparse-cu12==12.1.0.106
nvidia-nccl-cu12==2.19.3
nvidia-cusolver-cu12==11.4.5.107
nvidia-cufft-cu12==11.0.2.54
nvidia-curand-cu12==10.3.2.106
triton==2.2.0
PACKAGES
    exit 0
fi

if ! command -v git >/dev/null 2>&1; then
    set +u
    module load git/2.9.5
    set -u
fi

if [[ "$mode" == setup || "$mode" == prepare ]]; then
    (source "$project/setup.sh" "$project" "$runtime")
    if [[ "$mode" == prepare ]]; then
        fetch_checkpoint
    fi
    exit 0
fi

if [[ ! -f "$runtime/setup-complete" ]]; then
    echo 'Önce setup işini çalıştırın ve tamamlandığını kontrol edin.' >&2
    exit 1
fi

run="$project/runs/$SLURM_JOB_ID"
mkdir -p "$run"
export PYTHONPATH="$oft${PYTHONPATH:+:$PYTHONPATH}"
cd "$run"

nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv | tee gpu.csv
git -C "$oft" rev-parse HEAD > openvla-oft.commit
git -C "$libero" rev-parse HEAD > libero.commit
cp "$runtime/packages.txt" packages.txt
"$python" "$project/preflight.py" | tee preflight.log

if [[ "$mode" == smoke ]]; then
    exit 0
fi

printf '%s\n' "$checkpoint" > checkpoint.txt
"$python" "$oft/experiments/robot/libero/run_libero_eval.py" \
    --pretrained_checkpoint "$checkpoint" \
    --task_suite_name libero_10 \
    --num_trials_per_task 1 \
    --seed 7 \
    --local_log_dir "$run/eval-logs" 2>&1 | tee evaluation.log
checkpoint_ref="$HF_HOME/hub/models--moojink--openvla-7b-oft-finetuned-libero-10/refs/main"
if [[ -f "$checkpoint_ref" ]]; then
    cp "$checkpoint_ref" checkpoint.commit
fi
"$python" "$project/check_results.py" "$run"
