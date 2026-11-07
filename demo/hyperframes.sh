#!/usr/bin/env bash
set -euo pipefail

cli="${HYPERFRAMES_CLI:-$HOME/.npm/_npx/30acb1c3e824064a/node_modules/hyperframes/bin/hyperframes.mjs}"
test -f "$cli" || { printf '%s\n' 'The local HyperFrames CLI is missing.' >&2; exit 1; }
mountpoint -q '/run/media/masih/New Volume' || { printf '%s\n' 'Mount New Volume first.' >&2; exit 1; }
scratch='/run/media/masih/New Volume/dev/read-aloud-demo'
mkdir -p "$scratch/tmp" "$scratch/frame-cache"
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1 CI=1
export TMPDIR="$scratch/tmp" HYPERFRAMES_EXTRACT_CACHE_DIR="$scratch/frame-cache"
cores="$(python3 -c 'import os; print(",".join(map(str, sorted(os.sched_getaffinity(0))[:4])))')"
exec taskset -c "$cores" nice -n 19 node "$cli" "$@"
