#!/usr/bin/env python3
"""Resident Kokoro process. Requests and replies are tab-separated lines."""

import sys
import time
from pathlib import Path

from kokoro_onnx import Kokoro
import soundfile


def main():
    home = Path.home()
    model = Kokoro(
        str(home / ".cache/hyperframes/tts/models/kokoro-v1.0.onnx"),
        str(home / ".cache/hyperframes/tts/voices/voices-v1.0.bin"),
    )
    if "CUDAExecutionProvider" not in model.sess.get_providers():
        raise RuntimeError("Kokoro did not load the CUDA provider")
    model.create("Ready.", voice="af_heart", speed=1.0, lang="en-us")
    print("READY\tCUDAExecutionProvider", flush=True)

    for line in sys.stdin:
        generation, index = "0", "0"
        try:
            generation, index, speed, output, text = line.rstrip("\n").split("\t", 4)
            started = time.monotonic()
            samples, rate = model.create(text, voice="af_heart", speed=float(speed), lang="en-us")
            soundfile.write(output, samples, rate)
            elapsed_ms = round((time.monotonic() - started) * 1000)
            print(f"DONE\t{generation}\t{index}\t{elapsed_ms}", flush=True)
        except Exception as exc:
            message = f"Speech generation failed ({type(exc).__name__})"
            print(f"ERROR\t{generation}\t{index}\t{message}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Kokoro failed: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
