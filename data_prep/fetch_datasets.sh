#!/usr/bin/env bash
# Download the four public UAV datasets (AI-IO, NanoBench, TII-RATM, NeuroBEM) into $EXIMO_WORKSPACE/data/raw/<dataset>/.
# Download sizes are checked against the byte counts below; sha256 sums go to data/raw/_fetch_log.jsonl and can be
# compared with data_prep/manifest.json (the values at our download, 2026-10-14).
# Resumable: re-running skips finished steps (markers in data/raw/.state/) and
# wget -c / fetch_zip_members.py resume partial work.
#
#   DELETE_ARCHIVES=1 (default) removes each archive after a verified extraction.
#   WITH_NEUROBEM_RAW=1 (default) also fetches NeuroBEM raw_data.zip.
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=${EXIMO_WORKSPACE:-/workspace}
RAW=$ROOT/data/raw
STATE=$RAW/.state
MANIFESTS=$ROOT/data/manifests
LOG=$RAW/_fetch_log.jsonl
DELETE_ARCHIVES=${DELETE_ARCHIVES:-1}
WITH_NEUROBEM_RAW=${WITH_NEUROBEM_RAW:-1}
mkdir -p "$RAW" "$STATE" "$MANIFESTS"

log() {  # key value ... -> one JSON line in $LOG
  python3 -I -c 'import json,sys,datetime
d=dict(zip(sys.argv[1::2], sys.argv[2::2]))
d["time_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
print(json.dumps(d))' "$@" >> "$LOG"
}

step() { echo; echo "=== $(date -u +%FT%TZ) $*"; }

clone() {  # url dest dataset
  if [ -d "$2/.git" ]; then echo "already cloned: $2"; else git clone --depth 1 "$1" "$2"; fi
  log event clone dataset "$3" url "$1" commit "$(git -C "$2" rev-parse HEAD)" \
      files "$(git -C "$2" ls-files | wc -l)"
}

fetch() {  # url dest expected_bytes dataset
  wget -c --tries=10 --waitretry=10 --progress=dot:giga -O "$2" "$1"
  local size sha
  size=$(stat -c %s "$2")
  [ "$size" = "$3" ] || { echo "SIZE MISMATCH $2: got $size, expected $3" >&2; exit 1; }
  sha=$(sha256sum "$2" | cut -d' ' -f1)
  log event download dataset "$4" url "$1" file "$(basename "$2")" bytes "$size" sha256 "$sha"
  echo "ok $(basename "$2") $size B sha256=$sha"
}

finish_archive() {  # archive marker
  touch "$2"
  if [ "$DELETE_ARCHIVES" = 1 ]; then rm -f "$1"; echo "deleted archive $(basename "$1")"; fi
}

unzip_verified() {  # zip dest dataset ; CRC-tests every member, then extracts
  local n
  n=$(python3 -I - "$1" "$2" <<'EOF'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
bad = z.testzip()
if bad:
    sys.exit(f"CRC error in member {bad}")
z.extractall(sys.argv[2])  # extractall drops absolute paths and '..' components
print(sum(1 for i in z.infolist() if not i.is_dir()))
EOF
)
  log event extract dataset "$3" archive "$(basename "$1")" files "$n" verified "zip CRC32 (testzip)"
  echo "extracted $n files from $(basename "$1")"
}

# 1. NanoBench --------------------------------------------------------------
step "nanobench: shallow clone"
clone https://github.com/syediu/nanobench.git "$RAW/nanobench/repo" nanobench

# 2-3. AI-IO ----------------------------------------------------------------
step "ai_io: shallow clone"
clone https://github.com/SJTU-ViSYS-team/AI-IO.git "$RAW/ai_io/repo" ai_io

if [ ! -f "$STATE/ai_io_dataset.done" ]; then
  step "ai_io: release archive"
  A=$RAW/ai_io/_archives/AI-IO_dataset.tar.gz
  mkdir -p "$(dirname "$A")" "$RAW/ai_io/AI-IO_dataset"
  fetch https://github.com/SJTU-ViSYS-team/AI-IO/releases/download/v1.0/AI-IO_dataset.tar.gz "$A" 362936995 ai_io
  gzip -t "$A"
  n_list=$(tar -tzf "$A" | grep -vc '/$')
  tar -xzf "$A" -C "$RAW/ai_io/AI-IO_dataset" --no-same-owner
  n_ext=$(find "$RAW/ai_io/AI-IO_dataset" -type f | wc -l)
  [ "$n_list" = "$n_ext" ] || { echo "AI-IO file count mismatch: listed $n_list, extracted $n_ext" >&2; exit 1; }
  log event extract dataset ai_io archive AI-IO_dataset.tar.gz files "$n_ext" verified "gzip -t + tar listing count"
  echo "extracted $n_ext files"
  finish_archive "$A" "$STATE/ai_io_dataset.done"
fi

# 4. NeuroBEM ---------------------------------------------------------------
NB=https://download.ifi.uzh.ch/rpg/NeuroBEM
step "neurobem: index files"
mkdir -p "$RAW/neurobem/_archives"
fetch "$NB/Flights.txt" "$RAW/neurobem/Flights.txt" 7043 neurobem
fetch "$NB/testset.txt" "$RAW/neurobem/testset.txt" 338 neurobem
fetch "$NB/Readme.md"   "$RAW/neurobem/Readme.md"   6174 neurobem

neurobem_zip() {  # name bytes
  [ -f "$STATE/neurobem_$1.done" ] && return
  step "neurobem: $1"
  fetch "$NB/$1" "$RAW/neurobem/_archives/$1" "$2" neurobem
  unzip_verified "$RAW/neurobem/_archives/$1" "$RAW/neurobem" neurobem
  finish_archive "$RAW/neurobem/_archives/$1" "$STATE/neurobem_$1.done"
}
neurobem_zip processed_data.zip 657316788
[ "$WITH_NEUROBEM_RAW" = 1 ] && neurobem_zip raw_data.zip 455214377

# 5-6. TII-RATM -------------------------------------------------------------
step "tii_ratm: shallow clone"
clone https://github.com/tii-racing/drone-racing-dataset.git "$RAW/tii_ratm/repo" tii_ratm

TB=https://github.com/tii-racing/drone-racing-dataset/releases/download/v3.0.0
for part in autonomous:3 piloted:7; do
  name=${part%%:*}; n=${part##*:}
  [ -f "$STATE/tii_$name.done" ] && continue
  step "tii_ratm: $name (non-image members, range-extracted)"
  chunks=$(for i in $(seq -f '%02g' 1 "$n"); do printf '%s_zipchunk%s,' "$name" "$i"; done)
  python3 -I "$HERE/fetch_zip_members.py" --base "$TB" --chunks "${chunks%,}" \
      --out "$RAW/tii_ratm/v3.0.0" --exclude '/(camera|label)_flight-[^/]+\.zip$' \
      --index-out "$MANIFESTS/tii_ratm_v3.0.0_${name}_members.json"
  log event range_extract dataset tii_ratm release v3.0.0 part "$name" \
      index "data/manifests/tii_ratm_v3.0.0_${name}_members.json" verified "per-member zip CRC32 + size"
  touch "$STATE/tii_$name.done"
done

step "all done"
du -sh "$RAW"/*/
