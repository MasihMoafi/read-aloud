#!/usr/bin/env bash
set -euo pipefail

display="${DISPLAY:?Set DISPLAY to the hidden Xvfb display}"
[[ "$display" =~ ^:[0-9]+$ ]] || { printf '%s\n' 'Expected a local Xvfb display.' >&2; exit 1; }
pgrep -a -x Xvfb | rg -Fq "Xvfb $display " || { printf '%s\n' 'The display is not Xvfb.' >&2; exit 1; }
unset WAYLAND_DISPLAY WAYLAND_SOCKET
export XDG_SESSION_TYPE=x11
exec /snap/chromium/current/usr/lib/chromium-browser/chrome --ozone-platform=x11 "$@"
