#!/bin/bash -l
set -eo pipefail
module load git/2.9.5
exec git receive-pack "$@"
