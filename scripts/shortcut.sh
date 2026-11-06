#!/usr/bin/env bash
set -euo pipefail
export READ_ALOUD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
build="${READ_ALOUD_BUILD:-/run/media/masih/New Volume/dev/read-aloud}"
exec "$build/read-aloud" "$1"
