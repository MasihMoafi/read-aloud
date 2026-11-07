#!/usr/bin/env python3
"""Register GNOME shortcuts and login startup for a packaged app."""
import ast
import os
from pathlib import Path
import shlex
import subprocess
import sys

SCHEMA = 'org.gnome.settings-daemon.plugins.media-keys'
CUSTOM = SCHEMA + '.custom-keybinding'
BASE = '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/'
ITEMS = (('read', '<Super>r'), ('faster', '<Super>equal'), ('slower', '<Super>minus'))
OWN = {BASE + 'read-aloud-' + action + '/' for action, _ in ITEMS}
AUTOSTART = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'autostart/read-aloud.desktop'
MARKER = 'X-ReadAloud-Packaged=true'


def settings(*args):
    return subprocess.run(['gsettings', *args], check=True, text=True, capture_output=True).stdout.strip()


def schema(path):
    return CUSTOM + ':' + path


def main():
    action, launcher = sys.argv[1:]
    current = ast.literal_eval(settings('get', SCHEMA, 'custom-keybindings').removeprefix('@as '))
    if action == 'uninstall':
        settings('set', SCHEMA, 'custom-keybindings', repr([p for p in current if p not in OWN]))
        for path in OWN:
            settings('reset-recursively', schema(path))
        if AUTOSTART.exists() and MARKER in AUTOSTART.read_text():
            AUTOSTART.unlink()
        return
    if action != 'install':
        raise ValueError('Use install or uninstall')
    for path in current:
        if path not in OWN:
            binding = ast.literal_eval(settings('get', schema(path), 'binding')).lower()
            if binding in {key.lower() for _, key in ITEMS}:
                raise RuntimeError(f'Shortcut {binding} is already in use')
    if AUTOSTART.exists() and MARKER not in AUTOSTART.read_text():
        raise RuntimeError(f'Refusing to replace {AUTOSTART}')
    previous = {p: {k: ast.literal_eval(settings('get', schema(p), k)) for k in ('name', 'command', 'binding')} for p in OWN}
    try:
        for name, binding in ITEMS:
            path = BASE + 'read-aloud-' + name + '/'
            for key, value in (('name', 'Read Aloud: ' + name), ('command', shlex.quote(launcher) + ' --shortcut ' + name), ('binding', binding)):
                settings('set', schema(path), key, value)
        settings('set', SCHEMA, 'custom-keybindings', repr(current + [p for p in sorted(OWN) if p not in current]))
        AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
        quoted = '"' + launcher.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"'
        AUTOSTART.write_text('[Desktop Entry]\nType=Application\nName=Read Aloud\nExec=' + quoted + ' --background\n' + MARKER + '\n')
    except Exception:
        settings('set', SCHEMA, 'custom-keybindings', repr(current))
        for path, values in previous.items():
            for key, value in values.items():
                settings('set', schema(path), key, value)
        raise


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
