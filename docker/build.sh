#!/usr/bin/env bash
# Build the EX-IMO image. EXIMO_IMAGE overrides the tag (default ex-imo:latest).
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
docker build -t "${EXIMO_IMAGE:-ex-imo:latest}" -f "$HERE/Dockerfile" "$HERE"
