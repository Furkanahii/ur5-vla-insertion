#!/bin/bash
set -euo pipefail

project=${1:?}
runtime=${2:?}
environment="$runtime/env"
python="$environment/bin/python"
oft="$runtime/openvla-oft"
libero="$runtime/LIBERO"

exec 9>"$runtime/setup.lock"
flock 9
if [[ -f "$runtime/setup-complete" ]]; then
    echo 'Kurulum bu çalışma alanında hazır.'
    exit 0
fi

if ! command -v conda >/dev/null 2>&1; then
    set +u
    module load anaconda3/2025.06
    set -u
fi
if [[ ! -f "$environment/conda-meta/history" || ! -x "$python" ]]; then
    conda create --yes --prefix "$environment" --override-channels -c conda-forge python=3.10.14 pip
fi

fetch_revision() {
    local url=$1 revision=$2 destination=$3
    if [[ ! -d "$destination/.git" ]]; then
        git init --quiet "$destination"
    fi
    if ! git -C "$destination" cat-file -e "$revision^{commit}" 2>/dev/null; then
        git -C "$destination" fetch --depth=1 "$url" "$revision"
    fi
    git -C "$destination" checkout --quiet --detach "$revision"
}

fetch_revision https://github.com/moojink/openvla-oft.git e4287e94541f459edc4feabc4e181f537cd569a8 "$oft"
fetch_revision https://github.com/Lifelong-Robot-Learning/LIBERO.git 8f1084e3132a39270c3a13ebe37270a43ece2a01 "$libero"
fetch_revision https://github.com/moojink/transformers-openvla-oft.git bc339d9ad707454c0c115970db43c260067c61ab "$runtime/transformers"
fetch_revision https://github.com/moojink/dlimp_openvla.git 040105d256bd28866cc6620621a3d5f7b6b91b46 "$runtime/dlimp"

shopt -s nullglob
cuda_wheels=("$runtime/wheelhouse/"*.whl)
shopt -u nullglob
"$python" -m pip install --index-url https://download.pytorch.org/whl/cu121 \
    torch==2.2.0 torchvision==0.17.0 torchaudio==2.2.0 ${cuda_wheels[@]+"${cuda_wheels[@]}"}
mkdir -p "$runtime/legacy-wheels"
"$python" -m pip install tomli==2.0.1
# Read the upstream dependencies while using the exact shallow-cloned VCS revisions.
"$python" - "$oft/pyproject.toml" "$runtime" <<'PY'
from pathlib import Path
import sys

import tomli

runtime = Path(sys.argv[2]).resolve()
with open(sys.argv[1], 'rb') as source:
    requirements = tomli.load(source)['project']['dependencies']
local_sources = {'transformers': runtime / 'transformers', 'dlimp': runtime / 'dlimp'}
resolved = []
for requirement in requirements:
    name = requirement.split('@', 1)[0].strip()
    if name in local_sources:
        requirement = f'{name} @ {local_sources[name].as_uri()}'
    resolved.append(requirement)
(runtime / 'upstream-requirements.txt').write_text('\n'.join(resolved) + '\n')
PY
"$python" -m pip install --build-constraint "$project/build-constraints.txt" \
    --find-links "$runtime/legacy-wheels" \
    -c "$project/constraints.txt" \
    future==1.0.0 \
    -r "$runtime/upstream-requirements.txt" \
    -r "$oft/experiments/robot/libero/libero_requirements.txt"
"$python" -m pip install --no-deps --build-constraint "$project/build-constraints.txt" \
    --config-settings editable_mode=compat -e "$libero"
"$python" -m pip install --no-deps -e "$oft"
"$python" -m pip check
"$python" -m pip freeze > "$runtime/packages.txt"

# LIBERO reads YAML. A JSON object is also valid YAML and avoids an interactive prompt.
mkdir -p "$LIBERO_CONFIG_PATH"
"$python" - "$libero" "$LIBERO_CONFIG_PATH/config.yaml" <<'PY'
import json
from pathlib import Path
import sys

repo = Path(sys.argv[1]).resolve()
root = repo / 'libero' / 'libero'
paths = {
    'benchmark_root': root,
    'bddl_files': root / 'bddl_files',
    'init_states': root / 'init_files',
    'assets': root / 'assets',
    'datasets': repo / 'libero' / 'datasets',
}
for name, path in paths.items():
    if name != 'datasets' and not path.is_dir():
        raise SystemExit(f'LIBERO path missing: {path}')
Path(sys.argv[2]).write_text(json.dumps({key: str(path) for key, path in paths.items()}, indent=2) + '\n')
PY

touch "$runtime/setup-complete"
