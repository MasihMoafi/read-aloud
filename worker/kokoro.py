#!/usr/bin/env python3
"""Resident Kokoro process. Requests and replies are tab-separated lines."""

import os
import sys
import time
from pathlib import Path

from kokoro_onnx import Kokoro
import soundfile
from voices import english_voices, selected_voice, voices_path


def main():
    home = Path.home()
    bundled = Path(__file__).resolve().parent.parent / "models"
    cached = home / ".cache/hyperframes/tts"
    model_path = Path(os.environ.get("READ_ALOUD_MODEL", "")) if os.environ.get("READ_ALOUD_MODEL") else (
        bundled / "kokoro-v1.0.onnx" if (bundled / "kokoro-v1.0.onnx").is_file()
        else cached / "models/kokoro-v1.0.onnx"
    )
    voice_bundle = voices_path()
    if not model_path.is_file() or not voice_bundle.is_file():
        raise RuntimeError("Kokoro model or voices are missing. Install the model and voices first.")
    voices = english_voices(voice_bundle)
    model = Kokoro(
        str(model_path),
        str(voice_bundle),
    )
    if "CUDAExecutionProvider" not in model.sess.get_providers():
        raise RuntimeError("Kokoro did not load the CUDA provider")
    voice = selected_voice(voices)
    model.create("Ready.", voice=voice, speed=1.0, lang="en-gb" if voice.startswith("b") else "en-us")
    print("READY\tCUDAExecutionProvider", flush=True)

    for line in sys.stdin:
        generation, index = "0", "0"
        try:
            generation, index, speed, output, text = line.rstrip("\n").split("\t", 4)
            started = time.monotonic()
            voice = selected_voice(voices)
            samples, rate = model.create(text, voice=voice, speed=float(speed),
                                         lang="en-gb" if voice.startswith("b") else "en-us")
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
