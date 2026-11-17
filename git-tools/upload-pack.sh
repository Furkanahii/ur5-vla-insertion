#!/bin/bash -l
# SSH Git clients do not automatically load VALAR's Git module.
set -eo pipefail
module load git/2.9.5
exec git upload-pack "$@"
