#!/usr/bin/env python3
"""Compile into New Volume and stop the compiler if the CPU reaches 80 C."""

import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

output = Path(os.environ["READ_ALOUD_BUILD"]) / "read-aloud"
compiler = subprocess.Popen(
    ["rustc", "--edition", "2021", "-C", "opt-level=1", "core/main.rs", "-o", str(output)],
    start_new_session=True,
)
try:
    while compiler.poll() is None:
        data = subprocess.run(["sensors"], text=True, capture_output=True, check=True).stdout
        temperatures = re.findall(r"(?:Package id \d+|Core \d+):\s*\+([\d.]+)°C", data)
        if not temperatures or max(map(float, temperatures)) >= 80:
            print("CPU temperature unavailable or at least 80 C; stopping build.", file=sys.stderr)
            os.killpg(compiler.pid, signal.SIGTERM)
            compiler.wait()
            sys.exit(1)
        time.sleep(1)
    sys.exit(compiler.returncode)
except BaseException:
    if compiler.poll() is None:
        os.killpg(compiler.pid, signal.SIGTERM)
        compiler.wait()
    raise
