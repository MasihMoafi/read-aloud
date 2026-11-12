#!/usr/bin/env python3
"""A closed or long-idle Read Aloud leaves nothing running (no Electron, daemon or voice).

Uses the real Electron main process with a small fake daemon, so no voice model is loaded.
Run with: xvfb-run -a nice -n 19 python3 tests/app_lifetime.py
"""

import os
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(
    os.environ.get("READ_ALOUD_BUILD", "/run/media/masih/New Volume/dev/read-aloud")
)
WORK = Path.home() / "Work/tries"

FAKE_DAEMON = r"""#!/usr/bin/env python3
import os, socket, sys, threading
path = os.path.join(os.environ["READ_ALOUD_RUNTIME"], "daemon.sock")
os.makedirs(os.path.dirname(path), exist_ok=True)
server = socket.socket(socket.AF_UNIX)
server.bind(path)
server.listen()
subscribers, active = [], "0"
def state():
    return f"STATE\t{active}\t0\t0\t1\t\t1.0\n".encode()
def handle(client):
    global active
    line = client.makefile().readline().strip()
    if line == "SUBSCRIBE":
        subscribers.append(client)
        client.sendall(state())
    elif line in ("ACTIVE", "IDLE"):
        active = "1" if line == "ACTIVE" else "0"
        for subscriber in subscribers:
            subscriber.sendall(state())
        client.close()
    elif line == "SHUTDOWN":
        os.unlink(path)
        os._exit(0)
while True:
    connection, _ = server.accept()
    threading.Thread(target=handle, args=(connection,), daemon=True).start()
"""


def wait_for(predicate, description, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {description}")


def window_ids():
    result = subprocess.run(
        ["xdotool", "search", "--onlyvisible", "--name", "^Read Aloud$"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.split()


def wm_close():
    """Ask the window to close the way a window manager does (WM_DELETE_WINDOW)."""
    from Xlib import X, display, protocol

    screen = display.Display()
    window = screen.create_resource_object("window", int(window_ids()[0]))
    protocols, delete = (
        screen.intern_atom("WM_PROTOCOLS"),
        screen.intern_atom("WM_DELETE_WINDOW"),
    )
    window.send_event(
        protocol.event.ClientMessage(
            window=window,
            client_type=protocols,
            data=(32, [delete, X.CurrentTime, 0, 0, 0]),
        )
    )
    screen.flush()
    screen.close()


class App:
    def __init__(self, temp, *args, idle_ms=None):
        self.socket_path = temp / "runtime/daemon.sock"
        env = os.environ.copy()
        env.update(
            {
                "READ_ALOUD_BUILD": str(temp / "build"),
                "READ_ALOUD_ELECTRON": str(BUILD / "electron/electron"),
                "READ_ALOUD_RUNTIME": str(temp / "runtime"),
                "XDG_CONFIG_HOME": str(temp / "config"),
                "XDG_CACHE_HOME": str(temp / "cache"),
            }
        )
        env.pop("READ_ALOUD_IDLE_MS", None)
        if idle_ms is not None:
            env["READ_ALOUD_IDLE_MS"] = str(idle_ms)
        self.process = subprocess.Popen(
            [str(ROOT / "scripts/start.sh"), *args], env=env, start_new_session=True
        )
        wait_for(self.socket_path.exists, "daemon socket")

    def send(self, line):
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(self.socket_path))
            client.sendall(f"{line}\n".encode())

    def running(self):
        return self.process.poll() is None

    def gone(self):
        return not self.running() and not self.socket_path.exists()

    def stop(self):
        if self.running():
            try:
                self.send("SHUTDOWN")
                self.process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait(timeout=5)
        self.socket_path.unlink(missing_ok=True)


def check(temp, name, scenario, *args, **options):
    app = App(temp, *args, **options)
    try:
        scenario(app)
        print(f"passed: {name}")
    finally:
        app.stop()


def close_when_idle(app):
    wait_for(window_ids, "window")
    wm_close()
    wait_for(app.gone, "closed idle app to exit with its daemon")


def close_while_speaking(app):
    wait_for(window_ids, "window")
    app.send("ACTIVE")
    time.sleep(0.5)
    wm_close()
    wait_for(app.gone, "closing during speech to stop the app and daemon immediately")


def idle_exit(app):
    app.send("ACTIVE")
    time.sleep(2.5)
    assert app.running(), "The idle limit ended active speech"
    app.send("IDLE")
    wait_for(app.gone, "idle app to exit after the limit", timeout=10)


def visible_window_stays(app):
    wait_for(window_ids, "window")
    time.sleep(2.5)
    assert app.running() and window_ids(), (
        "The idle limit closed a window the user has open"
    )


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="read-aloud-lifetime-", dir=WORK) as name:
        temp = Path(name)
        build = temp / "build"
        build.mkdir()
        for file in ("index.html", "logo.png"):
            (build / file).symlink_to(BUILD / file)
        daemon = build / "read-aloud"
        daemon.write_text(FAKE_DAEMON)
        daemon.chmod(0o755)
        check(temp, "closing an idle app quits everything", close_when_idle, "--show")
        check(
            temp,
            "closing during speech immediately quits everything",
            close_while_speaking,
            "--show",
        )
        check(temp, "idle limit quits only after speech", idle_exit, idle_ms=1000)
        check(
            temp,
            "idle limit leaves an open window alone",
            visible_window_stays,
            "--show",
            idle_ms=1000,
        )


if __name__ == "__main__":
    main()
