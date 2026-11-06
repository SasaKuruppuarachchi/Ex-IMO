#!/usr/bin/env bash
# Run a job file on the GPU, a fixed number at a time. Finished jobs (<log> ends in "done:") are skipped, so it resumes.
#   scripts/run_queue.sh <jobs.txt> <parallel>
# A job line: <log file> <arguments for src/train_ex.py>
# Before each start, waits while total GPU utilisation is above GPU_START_BELOW (default 60).
# Stop gracefully: touch <jobs.txt>.stop (running jobs finish, no new ones start).
set -uo pipefail
JOBS=${1:?jobs file}; PAR=${2:-3}; LIMIT=${GPU_START_BELOW:-60}
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
util() { for _ in 1 2 3 4 5 6 7 8 9 10; do nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits | head -1; sleep 1; done | awk '{s+=$1} END {printf "%d", s/NR}'; }
while read -r log args; do
  [ -z "${log:-}" ] && continue
  case "$log" in \#*) continue;; esac
  [ -f "$JOBS.stop" ] && { echo "stop requested"; break; }
  if [ -f "$log" ] && grep -q "^done:" "$log"; then echo "skip $log"; continue; fi
  while [ "$(jobs -rp | wc -l)" -ge "$PAR" ]; do wait -n; done
  while [ "$(util)" -ge "$LIMIT" ]; do echo "$(date '+%T') GPU busy, waiting"; sleep 30; done
  mkdir -p "$(dirname "$log")"
  echo "$(date '+%F %T') start $log"
  EXIMO_GPU=1 EXIMO_THREADS=${EXIMO_THREADS:-4} "$HERE/../docker/run.sh" python3 src/train_ex.py $args > "$log" 2>&1 < /dev/null &  # docker run -i would read the job file
  sleep 60   # let the job reach steady GPU use before measuring again
done < "$JOBS"
wait
echo "$(date '+%F %T') queue finished"
