#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export READ_ALOUD_BUILD="${READ_ALOUD_BUILD:-/run/media/masih/New Volume/dev/read-aloud}"
cd "$root"
mountpoint -q '/run/media/masih/New Volume' || { printf '%s\n' 'Mount New Volume before building.' >&2; exit 1; }
case "$READ_ALOUD_BUILD" in
  '/run/media/masih/New Volume/'*) ;;
  *) printf '%s\n' 'Build output must be on New Volume.' >&2; exit 1 ;;
esac
available="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
(( available >= 8388608 )) || { printf '%s\n' 'At least 8 GiB of available memory is required.' >&2; exit 1; }
if pgrep -af '[n]ext build|[n]ode --test|[c]argo|[f]fmpeg'; then
  printf '%s\n' 'Another heavy job is running.' >&2
  exit 1
fi
mkdir -p "$READ_ALOUD_BUILD"
rustfmt --edition 2021 --check core/main.rs
python3 -c 'import ast,pathlib; ast.parse(pathlib.Path("worker/kokoro.py").read_text())'
node --check electron/main.cjs
node --check electron/preload.cjs
node --check scripts/build-ui.cjs
node scripts/build-ui.cjs --check
if [[ ! -x "$READ_ALOUD_BUILD/electron/electron" ]]; then
  electron_source="${READ_ALOUD_ELECTRON_SOURCE:-$HOME/Desktop/p/clocki/node_modules/electron/dist}"
  test -x "$electron_source/electron" || { printf '%s\n' 'The installed Electron runtime is missing.' >&2; exit 1; }
  mkdir -p "$READ_ALOUD_BUILD/electron"
  cp -r "$electron_source/." "$READ_ALOUD_BUILD/electron/"
fi
nice -n 19 python3 scripts/compile.py
nice -n 19 node scripts/build-ui.cjs
