#!/usr/bin/env python3
"""List and remember the English voices already in the local Kokoro bundle."""

import json
import os
from pathlib import Path
import re
import sys
import tempfile
from zipfile import BadZipFile, ZipFile

DEFAULT_VOICE = "af_heart"
VOICE_NAME = re.compile(r"(?:af|am|bf|bm)_[a-z0-9]+\Z")


def voices_path():
    configured = os.environ.get("READ_ALOUD_VOICES")
    if configured:
        return Path(configured)
    bundled = Path(__file__).resolve().parent.parent / "models/voices-v1.0.bin"
    if bundled.is_file():
        return bundled
    return Path.home() / ".cache/hyperframes/tts/voices/voices-v1.0.bin"


def english_voices(path=None):
    with ZipFile(path or voices_path()) as archive:
        voices = sorted(name[:-4] for name in archive.namelist()
                        if name.endswith(".npy") and VOICE_NAME.fullmatch(name[:-4]))
    if not voices:
        raise ValueError("The local voice bundle has no English voices.")
    return voices


def config_file():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "read-aloud/voice"


def selected_voice(voices):
    try:
        with config_file().open(encoding="utf-8") as saved:
            name = saved.read(128).strip()
    except (OSError, UnicodeError):
        name = ""
    if name in voices:
        return name
    return DEFAULT_VOICE if DEFAULT_VOICE in voices else voices[0]


def save_voice(name, voices):
    if name not in voices:
        raise ValueError("That voice is not in the local voice bundle.")
    target = config_file()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".voice-", dir=target.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as saved:
            saved.write(name + "\n")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    voices = english_voices()
    if sys.argv[1:] == ["status"]:
        pass
    elif len(sys.argv) == 3 and sys.argv[1] == "select":
        save_voice(sys.argv[2], voices)
    else:
        raise ValueError("Use status or select VOICE.")
    print(json.dumps({"voices": voices, "selected": selected_voice(voices)}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, BadZipFile) as error:
        print(f"Local voices unavailable: {error}", file=sys.stderr)
        sys.exit(1)
