#!/usr/bin/env python3
"""Check whether the demo still corresponds to the current player."""

import hashlib
import json
import os
from pathlib import Path
import sys

DEMO = Path(__file__).resolve().parent
ROOT = DEMO.parent
BUILD = Path(os.environ.get("READ_ALOUD_BUILD", "/run/media/masih/New Volume/dev/read-aloud"))
UI_FILES = {
    "electron/main.cjs": ROOT / "electron/main.cjs",
    "electron/preload.cjs": ROOT / "electron/preload.cjs",
    "renderer/index.html": ROOT / "renderer/index.html",
    "renderer/player.tsx": ROOT / "renderer/player.tsx",
    "renderer/styles.css": ROOT / "renderer/styles.css",
    "renderer/components/button.tsx": ROOT / "renderer/components/button.tsx",
    "assets/logo.svg": ROOT / "assets/logo.svg",
    "build/player.js": BUILD / "player.js",
    "build/player.css": BUILD / "player.css",
    "build/logo.svg": BUILD / "logo.svg",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ui_fingerprint():
    return {name: digest(path) for name, path in UI_FILES.items()}


def main():
    try:
        record = json.loads((DEMO / "current.json").read_text())
        current = ui_fingerprint()
        changed = [name for name in UI_FILES if record["ui"].get(name) != current[name]]
        if digest(DEMO / "Read-Aloud-demo.mp4") != record["video_sha256"]:
            changed.append("demo video")
    except (OSError, KeyError, json.JSONDecodeError) as error:
        print(f"Could not verify the demo: {error}", file=sys.stderr)
        return 1
    if changed:
        print("Demo needs review; changed since capture: " + ", ".join(changed), file=sys.stderr)
        return 1
    print("Demo matches the captured player and video.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
