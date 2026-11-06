#!/usr/bin/env python3
"""Reject repeated logo images in a new set of directions."""

import argparse
import hashlib
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).digest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--new", nargs="+", required=True)
parser.add_argument("--old", nargs="+", required=True)
args = parser.parse_args()

old_hashes = {digest(path) for path in args.old}
new_hashes = [digest(path) for path in args.new]
if len(new_hashes) != len(set(new_hashes)) or old_hashes.intersection(new_hashes):
    parser.exit(1, "The new logo directions repeat an existing image.\n")
print("The new logo directions are distinct from the earlier images.")
