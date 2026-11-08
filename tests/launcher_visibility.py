#!/usr/bin/env python3
"""Check launcher visibility using the real Electron app on an Xvfb display.

Run with: xvfb-run -a nice -n 19 python3 tests/launcher_visibility.py
Set READ_ALOUD_VISUAL_PROOF to save screenshots for inspection.
Set READ_ALOUD_LAUNCHER to check an installed desktop entry too.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPCTL = Path.home() / "Desktop/p/skills/app-control/appctl.py"
WORK = Path.home() / "Work/tries"


def wait_for(predicate, description, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {description}")


def visible():
    result = subprocess.run(
        ["xdotool", "search", "--onlyvisible", "--name", "^Read Aloud$"],
        capture_output=True,
        check=False,
    )
    return bool(result.stdout.strip())


def wm_close():
    """Ask the window to close the way a window manager does (WM_DELETE_WINDOW)."""
    from Xlib import X, display, protocol

    result = subprocess.run(
        ["xdotool", "search", "--onlyvisible", "--name", "^Read Aloud$"],
        capture_output=True,
        text=True,
        check=True,
    )
    screen = display.Display()
    window = screen.create_resource_object("window", int(result.stdout.split()[0]))
    protocols, delete = (
        screen.intern_atom("WM_PROTOCOLS"),
        screen.intern_atom("WM_DELETE_WINDOW"),
    )
    event = protocol.event.ClientMessage(
        window=window,
        client_type=protocols,
        data=(32, [delete, X.CurrentTime, 0, 0, 0]),
    )
    window.send_event(event)
    screen.flush()
    screen.close()


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
            # The shortcut can start an app that `process` does not own.
            if socket_path.exists():
                try:
                    send(socket_path, "SHUTDOWN")
                    wait_for(
                        lambda: not socket_path.exists(), "app to shut down", timeout=10
                    )
                    process.wait(timeout=10)
                except (OSError, AssertionError, subprocess.TimeoutExpired):
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
        env.update(
            {
                "XDG_CONFIG_HOME": str(temp / "config"),
                "XDG_CACHE_HOME": str(temp / "cache"),
                "READ_ALOUD_RUNTIME": str(temp / "runtime"),
                "READ_ALOUD_DEBUG_PORT": str(port),
                "APPCTL_ELPIS_PORT": str(port),
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "PATH": str(bin_dir) + os.pathsep + env["PATH"],
            }
        )
        proof = os.environ.get("READ_ALOUD_VISUAL_PROOF")

        def launch(show=False):
            return subprocess.Popen(
                [str(ROOT / "scripts/start.sh"), *(["--show"] if show else [])],
                env=env,
                start_new_session=True,
            )

        def appctl(*args):
            result = subprocess.run(
                [sys.executable, "-I", str(APPCTL), *args],
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=15,
            )
            if result.returncode:
                raise AssertionError(f"appctl {args}: {result.stderr}")
            return result.stdout

        def screenshots(name):
            if not proof:
                return
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{port}"
                )
                page = browser.contexts[0].pages[0]
                backgrounds = []
                for theme in ("light", "dark"):
                    page.emulate_media(color_scheme=theme)
                    page.wait_for_timeout(150)
                    backgrounds.append(
                        page.locator("main").evaluate(
                            "el => getComputedStyle(el).backgroundColor"
                        )
                    )
                    page.screenshot(
                        path=str(Path(proof) / f"{name}-{theme}.png"),
                        omit_background=True,
                    )
                assert backgrounds[0] != backgrounds[1], (
                    "Light and dark themes look the same"
                )
                original = page.evaluate("({width: innerWidth, height: innerHeight})")
                page.set_viewport_size({"width": 204, "height": 40})
                page.screenshot(path=str(Path(proof) / f"{name}-narrow.png"))
                page.set_viewport_size(original)

        def debug_ready():
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
                    f"http://127.0.0.1:{port}/json/version", timeout=0.2
                ):
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
            owner = subprocess.Popen(
                ["xclip", "-quiet", "-selection", "primary"],
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                owner.stdin.write(selection)
                owner.stdin.close()

                def selected():
                    result = subprocess.run(
                        ["xclip", "-out", "-selection", "primary"],
                        env=env,
                        capture_output=True,
                        timeout=2,
                        check=False,
                    )
                    return result.returncode == 0 and result.stdout == selection

                wait_for(selected, "selected text")
                subprocess.run(
                    [str(ROOT / "scripts/shortcut.sh"), "read"],
                    env=env,
                    check=True,
                    timeout=15,
                )
            finally:
                if owner.poll() is None:
                    os.killpg(owner.pid, signal.SIGTERM)
                owner.wait(timeout=5)

        process = launch(show=True)
        wait_for(
            lambda: socket_path.exists() and debug_ready() and visible(),
            "cold launcher window",
        )
        snapshot = appctl("see", "elpis")
        assert "Read Aloud" in snapshot and "Super+R to read" in snapshot, snapshot
        screenshots("idle")
        appctl("click", "elpis", "role:button=Voice")
        if proof:
            appctl("shot", "elpis", str(Path(proof) / "voice-menu.png"))
        appctl("click", "elpis", "role:menuitemradio=Emma · UK")
        wait_for(
            lambda: (temp / "config/read-aloud/voice").exists(), "voice choice to save"
        )
        assert (temp / "config/read-aloud/voice").read_text().strip() == "bf_emma"
        appctl("click", "elpis", "role:button=Close")
        wait_for(
            lambda: process.poll() is not None and not socket_path.exists(),
            "Close to end the app",
        )
        process = launch(show=True)
        wait_for(
            lambda: socket_path.exists() and debug_ready() and visible(),
            "window reopened by launcher",
        )
        # A window-manager close (Alt+F4) ends the app the same way.
        wm_close()
        wait_for(
            lambda: process.poll() is not None and not socket_path.exists(),
            "window-manager close to end the app",
        )

        # The shortcut alone must bring everything back after a close.
        read_selection()
        wait_for(
            lambda: socket_path.exists() and debug_ready(),
            "shortcut to start the closed app",
            timeout=30,
        )
        send(socket_path, "PAUSE")
        wait_for(lambda: 'button "Stop"' in appctl("see", "elpis"), "active player")
        screenshots("player")

        controls = json.loads(
            appctl(
                "eval",
                "elpis",
                """(() => {
          const stop = document.querySelector('[aria-label="Stop"]');
          const voice = document.querySelector('[aria-label="Voice"]');
          const speed = document.querySelector('[aria-label="Speed"]');
          const icon = speed.querySelector('svg');
          const label = speed.querySelector('span');
          return { width: innerWidth, gap: speed.getBoundingClientRect().left - voice.getBoundingClientRect().right,
            icon: icon?.classList.contains('lucide-zap'), iconBeforeLabel: icon?.getBoundingClientRect().right <= label.getBoundingClientRect().left,
            clipped: speed.getBoundingClientRect().right > innerWidth || voice.getBoundingClientRect().left < stop.getBoundingClientRect().right };
        })()""",
            )
        )
        assert (
            controls["width"] <= 220
            and controls["gap"] == 2
            and controls["icon"]
            and controls["iconBeforeLabel"]
            and not controls["clipped"]
        ), controls

        def window_height():
            return json.loads(appctl("eval", "elpis", "window.innerHeight"))

        bar_height = window_height()
        appctl("click", "elpis", "role:button=Voice")
        appctl("click", "elpis", "role:button=Speed")
        assert 'menu "Voices"' not in appctl("see", "elpis")
        appctl("click", "elpis", "role:button=Voice")
        appctl("click", "elpis", "role:menuitemradio=Michael · US")
        wait_for(
            lambda: (
                (temp / "config/read-aloud/voice").read_text().strip() == "am_michael"
            ),
            "playing voice choice",
        )
        wait_for(lambda: window_height() == bar_height, "voice menu to close")
        for label, shown in (("1.5×", "1.5×"), ("2.0×", "2.0×"), ("Normal", "1.0×")):
            appctl("click", "elpis", "role:button=Speed")
            wait_for(lambda: window_height() > bar_height, "speed menu to open")
            if proof and label == "2.0×":
                appctl("shot", "elpis", str(Path(proof) / "player-menu.png"))
            appctl("click", "elpis", f"role:menuitemradio={label}")
            wait_for(
                lambda shown=shown: (
                    json.loads(
                        appctl(
                            "eval",
                            "elpis",
                            "document.querySelector('[aria-label=\"Speed\"]').textContent",
                        )
                    )
                    == shown
                ),
                f"speed {shown}",
            )
            wait_for(lambda: window_height() == bar_height, "speed menu to close")
        appctl("click", "elpis", "role:button=Voice")
        appctl("click", "elpis", "role:button=Stop")
        wait_for(lambda: not visible(), "player to hide after stopping")
        reopen()
        wait_for(visible, "player to reopen after stopping")
        wait_for(
            lambda: window_height() == bar_height, "voice menu to close after stopping"
        )
        shutdown()

        process = launch()
        wait_for(lambda: socket_path.exists() and debug_ready(), "login startup")
        time.sleep(0.5)
        assert not visible(), "Login startup displayed a window"
        launcher = os.environ.get("READ_ALOUD_LAUNCHER")
        if launcher:
            subprocess.run(["gio", "launch", launcher], env=env, check=True, timeout=10)
        else:
            reopen()
        wait_for(visible, "launcher to show the login-started app")
        assert "Super+R to read" in appctl("see", "elpis")
        appctl("click", "elpis", "role:button=Voice")
        voice = json.loads(
            appctl(
                "eval",
                "elpis",
                """(() => [...document.querySelectorAll('[role="menuitemradio"]')].find(e => e.getAttribute('aria-checked') === 'true')?.textContent.trim())()""",
            )
        )
        assert voice == "Michael · US", voice
        print(
            "Cold launch, close, reopen, voice choice, speed, and hidden login startup passed."
        )
    finally:
        try:
            shutdown()
        finally:
            subprocess.run(["gio", "trash", str(temp)], check=True)


if __name__ == "__main__":
    main()
