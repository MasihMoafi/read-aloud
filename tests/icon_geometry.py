#!/usr/bin/env python3
"""Check that the app icon preserves the selected artwork's proportions."""

import math
import os
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(os.environ.get("READ_ALOUD_BUILD", "/run/media/masih/New Volume/dev/read-aloud"))


def aspect(path):
    with Image.open(path) as image:
        alpha = image.convert("RGBA").getchannel("A")
        bounds = alpha.point(lambda value: 255 if value >= 64 else 0).getbbox()
    if not bounds:
        raise AssertionError(f"{path} has no visible artwork")
    return (bounds[2] - bounds[0]) / (bounds[3] - bounds[1])


source = aspect(ROOT / "design/logo-source.png")
icon_path = BUILD / "logo.png"
with Image.open(icon_path) as icon:
    if icon.size != (256, 256):
        raise AssertionError(f"App icon is {icon.size}, expected 256×256")
icon_aspect = aspect(icon_path)
if abs(math.log(icon_aspect / source)) > .07:
    raise AssertionError(f"App icon stretches the artwork: {icon_aspect:.2f} versus {source:.2f}")
print("App icon preserves the chosen artwork's proportions.")
