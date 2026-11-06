#!/usr/bin/env python3
"""Register or remove this app's GNOME shortcuts and login entry."""

import ast
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM = f"{SCHEMA}.custom-keybinding"
BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
ITEMS = (
    ("read-aloud-read", "Read Aloud: read selection", "<Super>r", "read"),
    ("read-aloud-faster", "Read Aloud: faster", "<Super>equal", "faster"),
    ("read-aloud-slower", "Read Aloud: slower", "<Super>minus", "slower"),
)
OWN = {f"{BASE}{item[0]}/" for item in ITEMS}
AUTOSTART = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart/read-aloud.desktop"
MARKER = f"X-ReadAloud-Owner={ROOT}"


def settings(*args):
    return subprocess.run(["gsettings", *args], text=True, capture_output=True, check=True).stdout.strip()


def paths():
    value = settings("get", SCHEMA, "custom-keybindings")
    return ast.literal_eval(value.removeprefix("@as "))


def schema(path):
    return f"{CUSTOM}:{path}"


def get(path, key):
    return ast.literal_eval(settings("get", schema(path), key))


def set_value(path, key, value):
    settings("set", schema(path), key, value)


def install():
    build = Path(os.environ.get("READ_ALOUD_BUILD", "/run/media/masih/New Volume/dev/read-aloud"))
    for item in (build / "read-aloud", build / "index.html", build / "player.js"):
        if not item.exists():
            raise RuntimeError(f"Build the app first: {item} is missing")
    current = paths()
    for path in current:
        if path in OWN:
            continue
        binding = get(path, "binding").lower()
        if binding in {item[2].lower() for item in ITEMS}:
            raise RuntimeError(f"Shortcut {binding} is already used by {get(path, 'name')}")
    if AUTOSTART.exists() and MARKER not in AUTOSTART.read_text():
        raise RuntimeError(f"Refusing to replace {AUTOSTART}")

    saved = {path: {key: get(path, key) for key in ("name", "command", "binding")} for path in OWN}
    try:
        for name, label, binding, action in ITEMS:
            path = f"{BASE}{name}/"
            set_value(path, "name", label)
            set_value(path, "command", f"{ROOT}/scripts/shortcut.sh {action}")
            set_value(path, "binding", binding)
        settings("set", SCHEMA, "custom-keybindings", repr(current + [p for p in sorted(OWN) if p not in current]))
        AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART.write_text(
            "[Desktop Entry]\nType=Application\nName=Read Aloud\n"
            f"Exec={ROOT}/scripts/start.sh\nX-GNOME-Autostart-enabled=true\n{MARKER}\n"
        )
    except Exception:
        settings("set", SCHEMA, "custom-keybindings", repr(current))
        for path, values in saved.items():
            for key, value in values.items():
                set_value(path, key, value)
        raise
    print("Installed three GNOME shortcuts and the login entry.")


def uninstall():
    current = paths()
    settings("set", SCHEMA, "custom-keybindings", repr([path for path in current if path not in OWN]))
    for path in OWN:
        settings("reset-recursively", schema(path))
    if AUTOSTART.exists() and MARKER in AUTOSTART.read_text():
        subprocess.run(["gio", "trash", str(AUTOSTART)], check=True)
    runtime = Path(os.environ.get("READ_ALOUD_RUNTIME", Path(os.environ["XDG_RUNTIME_DIR"]) / "read-aloud"))
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2)
            client.connect(str(runtime / "daemon.sock"))
            client.sendall(b"SHUTDOWN\n")
            client.shutdown(socket.SHUT_WR)
            client.recv(1024)
    except (FileNotFoundError, ConnectionRefusedError):
        pass
    print("Removed Read Aloud shortcuts and login entry; other shortcuts remain.")


try:
    if sys.argv[1:] == ["install"]:
        install()
    elif sys.argv[1:] == ["uninstall"]:
        uninstall()
    else:
        raise RuntimeError("Use setup.py install or setup.py uninstall")
except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
    print(error, file=sys.stderr)
    sys.exit(1)
