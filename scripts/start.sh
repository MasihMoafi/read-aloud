#!/usr/bin/env bash
set -euo pipefail

export READ_ALOUD_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export READ_ALOUD_BUILD="${READ_ALOUD_BUILD:-/run/media/masih/New Volume/dev/read-aloud}"
electron="${READ_ALOUD_ELECTRON:-$READ_ALOUD_BUILD/electron/electron}"
log_dir="${XDG_CACHE_HOME:-$HOME/.cache}/read-aloud"
mkdir -p "$log_dir"
unset ELECTRON_RUN_AS_NODE
exec "$electron" --ozone-platform=x11 "$READ_ALOUD_ROOT" "$@" >>"$log_dir/app.log" 2>&1
