#!/usr/bin/env python3
"""Check each extracted package for its runtime and forbidden payloads."""
import os
from pathlib import Path
import subprocess
import sys

for argument in sys.argv[1:]:
    package = Path(argument)
    runtimes = list(package.rglob('runtime/bin/python3'))
    cores = list(package.rglob('build/read-aloud'))
    if len(runtimes) != 1 or len(cores) != 1 or not os.access(cores[0], os.X_OK):
        raise SystemExit(f'{package}: expected one executable runtime and Rust core')
    forbidden = []
    for path in package.rglob('*'):
        name = path.name.lower()
        if name in ('kokoro-v1.0.onnx', 'voices-v1.0.bin') or name.startswith(('libcuda.', 'libcudnn', 'libcublas', 'onnxruntime_gpu', 'nvidia_cu')):
            forbidden.append(str(path))
    if forbidden:
        raise SystemExit(f'{package}: forbidden payloads: {forbidden}')
    subprocess.run([str(runtimes[0]), '-c', 'import kokoro_onnx, soundfile, onnxruntime as o; assert "CPUExecutionProvider" in o.get_available_providers(); assert "CUDAExecutionProvider" not in o.get_available_providers()'], check=True)
    print(f'{package}: CPU runtime and core present; no model files or NVIDIA libraries found')
