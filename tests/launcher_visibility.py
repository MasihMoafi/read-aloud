#!/usr/bin/env python3
"""Check launcher visibility using the real Electron app on an Xvfb display.

Run with: xvfb-run -a nice -n 19 python3 tests/launcher_visibility.py
Set READ_ALOUD_VISUAL_PROOF to save screenshots for inspection.
Set READ_ALOUD_LAUNCHER to check an installed desktop entry too.
"""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
APPCTL = Path.home() / "Desktop/p/skills/app-control/appctl.py"
WORK = Path.home() / "Work/tries"


def wait_for(predicate, description, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError(f"Timed out waiting for {description}")


def visible():
    result = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "^Read Aloud$"], capture_output=True)
    return bool(result.stdout.strip())


def send(path, name, body=""):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(3)
        client.connect(str(path))
        client.sendall((name + "\n" + body).encode())
        client.shutdown(socket.SHUT_WR)
        if not client.recv(1024).startswith(b"OK"):
            raise AssertionError(f"{name} was rejected")


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="read-aloud-launcher-", dir=WORK))
    process = None
    socket_path = temp / "runtime/daemon.sock"

    def shutdown():
        nonlocal process
        if process is None:
            return
        try:
            if process.poll() is None:
                try:
                    send(socket_path, "SHUTDOWN")
                    process.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            if process.poll() is None:
                process.wait(timeout=5)
            process = None

    try:
        bin_dir = temp / "bin"
        bin_dir.mkdir()
        player = bin_dir / "pw-play"
        player.write_text("#!/bin/sh\nexit 1\n")
        player.chmod(0o755)
        with socket.socket() as port_socket:
            port_socket.bind(("127.0.0.1", 0))
            port = port_socket.getsockname()[1]
        env = os.environ.copy()
        env.update({
            "XDG_CONFIG_HOME": str(temp / "config"),
            "XDG_CACHE_HOME": str(temp / "cache"),
            "READ_ALOUD_RUNTIME": str(temp / "runtime"),
            "READ_ALOUD_DEBUG_PORT": str(port),
            "APPCTL_ELPIS_PORT": str(port),
            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
            "PATH": str(bin_dir) + os.pathsep + env["PATH"],
        })
        proof = os.environ.get("READ_ALOUD_VISUAL_PROOF")

        def launch(show=False):
            return subprocess.Popen([str(ROOT / "scripts/start.sh"), *(["--show"] if show else [])],
                                    env=env, start_new_session=True)

        def appctl(*args):
            return subprocess.run(["python3", "-I", str(APPCTL), *args], env=env, text=True,
                                  capture_output=True, check=True, timeout=15).stdout

        def screenshots(name):
            if not proof:
                return
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                page = browser.contexts[0].pages[0]
                backgrounds = []
                for theme in ("light", "dark"):
                    page.emulate_media(color_scheme=theme)
                    page.wait_for_timeout(150)
                    backgrounds.append(page.locator("main").evaluate("el => getComputedStyle(el).backgroundColor"))
                    page.screenshot(path=str(Path(proof) / f"{name}-{theme}.png"))
                assert backgrounds[0] != backgrounds[1], "Light and dark themes look the same"
                page.set_viewport_size({"width": 320, "height": 64})
                page.screenshot(path=str(Path(proof) / f"{name}-narrow.png"))
                page.set_viewport_size({"width": 344, "height": 64})

        def debug_ready():
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                        f"http://127.0.0.1:{port}/json/version", timeout=.2):
                    return True
            except OSError:
                return False

        def reopen():
            second = launch(show=True)
            try:
                assert second.wait(timeout=10) == 0, "The second launcher failed"
            finally:
                try:
                    os.killpg(second.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

        def read_selection():
            selection = b"Launcher visibility test."
            owner = subprocess.Popen(["xclip", "-quiet", "-selection", "primary"], env=env,
                                     stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                owner.stdin.write(selection)
                owner.stdin.close()

                def selected():
                    result = subprocess.run(["xclip", "-out", "-selection", "primary"], env=env,
                                            capture_output=True, timeout=2)
                    return result.returncode == 0 and result.stdout == selection

                wait_for(selected, "selected text")
                subprocess.run([str(ROOT / "scripts/shortcut.sh"), "read"], env=env, check=True, timeout=15)
            finally:
                if owner.poll() is None:
                    os.killpg(owner.pid, signal.SIGTERM)
                owner.wait(timeout=5)

        process = launch(show=True)
        wait_for(lambda: socket_path.exists() and debug_ready() and visible(), "cold launcher window")
        snapshot = appctl("see", "elpis")
        assert "Read Aloud" in snapshot and "Select text, then press Windows+R" in snapshot, snapshot
        screenshots("idle")
        appctl("click", "elpis", "role:button=Close")
        wait_for(lambda: not visible(), "closed window to hide")
        assert process.poll() is None, "Close stopped the resident app"
        reopen()
        wait_for(visible, "window reopened by launcher")

        read_selection()
        send(socket_path, "PAUSE")
        wait_for(lambda: "button \"Stop\"" in appctl("see", "elpis"), "active player")
        screenshots("player")
        for speed in ("1.25×", "1.5×", "1.75×", "2.0×"):
            appctl("click", "elpis", "role:button=Increase speed")
            wait_for(lambda: json.loads(appctl("eval", "elpis", "document.querySelector('output').textContent")) == speed,
                     f"speed {speed}")
        assert json.loads(appctl("eval", "elpis", "document.querySelector('[aria-label=\"Increase speed\"]').disabled"))
        if proof:
            appctl("shot", "elpis", str(Path(proof) / "player-max.png"))
        appctl("click", "elpis", "role:button=Stop")
        wait_for(lambda: not visible(), "player to hide after stopping")
        shutdown()

        process = launch()
        wait_for(lambda: socket_path.exists() and debug_ready(), "login startup")
        time.sleep(.5)
        assert not visible(), "Login startup displayed a window"
        launcher = os.environ.get("READ_ALOUD_LAUNCHER")
        if launcher:
            subprocess.run(["gio", "launch", launcher], env=env, check=True, timeout=10)
        else:
            reopen()
        wait_for(visible, "launcher to show the login-started app")
        assert "Select text, then press Windows+R" in appctl("see", "elpis")
        print("Cold launch, close, reopen, player stop, and hidden login startup passed.")
    finally:
        try:
            shutdown()
        finally:
            subprocess.run(["gio", "trash", str(temp)], check=True)


if __name__ == "__main__":
    main()
