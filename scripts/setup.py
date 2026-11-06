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
LAUNCHER = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications/read-aloud.desktop"
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
    subprocess.run(["node", str(ROOT / "scripts/check-logo-approval.cjs")], check=True)
    for item in (build / "read-aloud", build / "index.html", build / "player.js", build / "player.css", build / "logo.svg", build / "logo.png"):
        if not item.exists():
            raise RuntimeError(f"Build the app first: {item} is missing")
    if (build / "logo.svg").read_bytes() != (ROOT / "assets/logo.svg").read_bytes():
        raise RuntimeError("Build the app first: its logo is out of date")
    current = paths()
    for path in current:
        if path in OWN:
            continue
        binding = get(path, "binding").lower()
        if binding in {item[2].lower() for item in ITEMS}:
            raise RuntimeError(f"Shortcut {binding} is already used by {get(path, 'name')}")
    entries = (AUTOSTART, LAUNCHER)
    for path in entries:
        if path.exists() and MARKER not in path.read_text():
            raise RuntimeError(f"Refusing to replace {path}")

    saved = {path: {key: get(path, key) for key in ("name", "command", "binding")} for path in OWN}
    previous_entries = {path: path.read_text() if path.exists() else None for path in entries}
    try:
        for name, label, binding, action in ITEMS:
            path = f"{BASE}{name}/"
            set_value(path, "name", label)
            set_value(path, "command", f"{ROOT}/scripts/shortcut.sh {action}")
            set_value(path, "binding", binding)
        settings("set", SCHEMA, "custom-keybindings", repr(current + [p for p in sorted(OWN) if p not in current]))
        for path in entries:
            path.parent.mkdir(parents=True, exist_ok=True)
            show = " --show" if path == LAUNCHER else ""
            path.write_text(
                "[Desktop Entry]\nType=Application\nName=Read Aloud\nComment=Read selected text with Super+R\n"
                f"Exec={ROOT}/scripts/start.sh{show}\nIcon={ROOT}/assets/logo.svg\n"
                f"X-GNOME-Autostart-enabled=true\n{MARKER}\n"
            )
    except Exception:
        settings("set", SCHEMA, "custom-keybindings", repr(current))
        for path, values in saved.items():
            for key, value in values.items():
                set_value(path, key, value)
        for path, previous in previous_entries.items():
            if previous is None and path.exists():
                subprocess.run(["gio", "trash", str(path)], check=True)
            elif previous is not None:
                path.write_text(previous)
        raise
    print("Installed three GNOME shortcuts, the launcher, and the login entry.")


def uninstall():
    current = paths()
    settings("set", SCHEMA, "custom-keybindings", repr([path for path in current if path not in OWN]))
    for path in OWN:
        settings("reset-recursively", schema(path))
    for path in (AUTOSTART, LAUNCHER):
        if path.exists() and MARKER in path.read_text():
            subprocess.run(["gio", "trash", str(path)], check=True)
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
    print("Removed Read Aloud shortcuts, launcher, and login entry; other shortcuts remain.")


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
