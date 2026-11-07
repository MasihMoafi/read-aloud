#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
archive='cpython-3.12.9+20250317-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz'
url="https://github.com/astral-sh/python-build-standalone/releases/download/20250317/$archive"
mkdir -p "$root/staging/runtime"
curl --fail --location --retry 3 "$url" -o "$RUNNER_TEMP/$archive"
curl --fail --location --retry 3 "$url.sha256" -o "$RUNNER_TEMP/python.sha256"
(cd "$RUNNER_TEMP" && printf '%s  %s\n' "$(cat python.sha256)" "$archive" | sha256sum -c -)
tar -xzf "$RUNNER_TEMP/$archive" --strip-components=1 -C "$root/staging/runtime"
"$root/staging/runtime/bin/python3" -m pip install --only-binary=:all: --no-cache-dir -r "$root/packaging/requirements.txt"
"$root/staging/runtime/bin/python3" -m pip check
"$root/staging/runtime/bin/python3" -c 'import onnxruntime as o, kokoro_onnx, soundfile; assert "CPUExecutionProvider" in o.get_available_providers(); assert "CUDAExecutionProvider" not in o.get_available_providers()'
