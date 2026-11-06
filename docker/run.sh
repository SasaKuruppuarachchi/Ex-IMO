#!/usr/bin/env bash
# Run a command in the EX-IMO image with the repo, the datasets and the outputs mounted.
#   docker/run.sh python3 src/train_ex.py ...          CPU (default)
#   EXIMO_GPU=1 docker/run.sh python3 src/train_ex.py ...
#
# EXIMO_DATA     host folder holding raw/, clean/, processed/ (default <repo>/../eximo_data); mounted at /workspace/data
# EXIMO_OUT      host folder for converted data and results (default <repo>/../eximo_out); mounted at the same path
# EXIMO_IMAGE    image (default ex-imo:latest, see docker/build.sh)
# EXIMO_THREADS  CPU threads per process (default 4)
# docker/local.env, if present, is sourced first (machine-specific settings, git-ignored).
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(dirname "$HERE")
[ -f "$HERE/local.env" ] && . "$HERE/local.env"
DATA=${EXIMO_DATA:-$(dirname "$REPO")/eximo_data}
OUT=${EXIMO_OUT:-$(dirname "$REPO")/eximo_out}
THREADS=${EXIMO_THREADS:-4}
mkdir -p "$DATA" "$OUT"

args=(--rm -i --ipc=host
      -v "$REPO:/workspace/EX-IMO"
      -v "$DATA:/workspace/data${EXIMO_DATA_MODE:+:$EXIMO_DATA_MODE}"
      -v "$OUT:$OUT"
      -w /workspace/EX-IMO
      --user "$(id -u):$(id -g)" -e HOME=/tmp -e USER="$(id -un)" -e MPLBACKEND=Agg
      -e PYTHONPATH=/workspace/EX-IMO/src -e PYTHONDONTWRITEBYTECODE=1
      -e EXIMO_WORKSPACE=/workspace -e EXIMO_OUT="$OUT"
      -e OMP_NUM_THREADS="$THREADS" -e MKL_NUM_THREADS="$THREADS" -e NUMBA_NUM_THREADS="$THREADS")
for m in ${EXIMO_EXTRA_MOUNTS:-}; do args+=(-v "$m"); done
if [ "${EXIMO_GPU:-0}" = 1 ]; then
  args+=(--gpus all)
else
  args+=(-e CUDA_VISIBLE_DEVICES=)
fi
exec docker run "${args[@]}" "${EXIMO_IMAGE:-ex-imo:latest}" "$@"
