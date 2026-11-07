#!/usr/bin/env python3
"""Record a real Read Aloud session on Xvfb without capturing any input device.

Run through xvfb-run with a 1280×720 screen. The app, Chromium profile, primary
selection and speech output are isolated; the app's own generated WAV supplies
the film's audio. All processes and the temporary PipeWire sink are removed.
"""

import base64
import json
import os
from pathlib import Path
import queue
import re
import select
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request

from playwright.sync_api import sync_playwright
from Xlib import X, XK, display

from check_current import ui_fingerprint

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
OUTPUT = Path("/run/media/masih/New Volume/dev/read-aloud-demo")
SAMPLE = "Select a passage, press Super R, and listen as you work."


def run(*args, env=None):
    return subprocess.run(args, env=env, text=True, capture_output=True, check=True, timeout=10).stdout


def temperature():
    for name in Path("/sys/class/hwmon").glob("hwmon*/name"):
        if name.read_text().strip() == "coretemp":
            return max(int(p.read_text()) / 1000 for p in name.parent.glob("temp*_input"))
    raise RuntimeError("CPU temperature is unavailable")


def check_heat():
    if temperature() >= 78:
        raise RuntimeError("CPU reached 78°C; stopping the capture")


def wait_for(predicate, label, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        check_heat()
        result = predicate()
        if result:
            return result
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for {label}")


def rest(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        check_heat()
        time.sleep(max(0, min(0.2, end - time.monotonic())))


def free_port():
    with socket.socket() as port:
        port.bind(("127.0.0.1", 0))
        return port.getsockname()[1]


def debug_ready(port):
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
            f"http://127.0.0.1:{port}/json/version", timeout=0.3
        ):
            return True
    except OSError:
        return False


def state(path):
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(1)
            client.connect(str(path))
            client.sendall(b"SUBSCRIBE\n")
            return client.recv(1024).decode().strip().split("\t")
    except OSError:
        return []


def send(path, command):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(2)
        client.connect(str(path))
        client.sendall((command + "\n").encode())
        client.shutdown(socket.SHUT_WR)
        if not client.recv(1024).startswith(b"OK"):
            raise RuntimeError(f"{command} was rejected")


def sink_id(name):
    listing = run("pw-cli", "ls", "Node")
    for block in re.split(r"(?=\n\s*id \d+, type PipeWire:Interface:Node)", listing):
        if f'node.name = "{name}"' in block:
            return re.search(r"\bid (\d+),", block).group(1)
    return None


def stop(process, sig=signal.SIGTERM):
    if process is None:
        return
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass
    if process.poll() is None:
        process.wait(timeout=10)


def main():
    if not os.environ.get("DISPLAY", "").startswith(":"):
        raise RuntimeError("Run this capture on an Xvfb display")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="capture-", dir=OUTPUT))
    take = Path(tempfile.mkdtemp(prefix="take-", dir=OUTPUT))
    success = False
    app = chrome = recorder = None
    sink = None
    key_display = None
    key_thread = None
    stop_keys = threading.Event()
    key_events = queue.Queue()
    log = None
    try:
        ui_before = ui_fingerprint()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "AI_AGENT"))}
        env.pop("WAYLAND_DISPLAY", None)
        env.pop("WAYLAND_SOCKET", None)
        app_port, browser_port = free_port(), free_port()
        while browser_port == app_port:
            browser_port = free_port()
        sink_name = f"read_aloud_demo_{os.getpid()}"
        player_name = f"read_aloud_demo_player_{os.getpid()}"
        runtime = temp / "runtime"
        env.update({
            "XDG_SESSION_TYPE": "x11",
            "XDG_CONFIG_HOME": str(temp / "config"),
            "XDG_CACHE_HOME": str(temp / "cache"),
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path={temp}/no-session-bus",
            "READ_ALOUD_RUNTIME": str(runtime),
            "READ_ALOUD_DEBUG_PORT": str(app_port),
            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
            "DEMO_OUTPUT": str(take), "DEMO_SINK": sink_name, "DEMO_PLAYER": player_name,
        })
        bin_dir = temp / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "pw-play"
        wrapper.write_text('''#!/usr/bin/env python3
import json, os, shutil, sys, time
from pathlib import Path
out = Path(os.environ["DEMO_OUTPUT"])
shutil.copyfile(sys.argv[-1], out / "speech.wav")
(out / "speech-start.json").write_text(json.dumps({"time": time.monotonic()}))
os.execv("/usr/bin/pw-play", ["pw-play", "--target", os.environ["DEMO_SINK"],
    "--properties", "{ node.name = " + os.environ["DEMO_PLAYER"] + " }", *sys.argv[1:]])
''')
        wrapper.chmod(0o755)
        env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]

        run("pw-cli", "create-node", "adapter",
            f'{{ factory.name = support.null-audio-sink node.name = "{sink_name}" '
            'media.class = Audio/Sink audio.position = [ FL FR ] object.linger = true priority.session = 0 }')
        sink = wait_for(lambda: sink_id(sink_name), "isolated audio sink")

        chrome = subprocess.Popen([
            str(ROOT / "scripts/hidden-chromium.sh"), f"--user-data-dir={temp / 'chromium'}",
            f"--remote-debugging-port={browser_port}", "--no-first-run", "--no-default-browser-check",
            "--disable-background-networking", "--disable-extensions", "--disable-sync",
            "--disable-dev-shm-usage", "--window-size=1280,720", "--window-position=0,0",
            f"--app={DEMO.joinpath('fixture.html').as_uri()}",
        ], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        wait_for(lambda: debug_ready(browser_port), "hidden Chromium")

        app = subprocess.Popen([str(ROOT / "scripts/start.sh")], env=env, start_new_session=True)
        socket_path = runtime / "daemon.sock"
        wait_for(lambda: len(state(socket_path)) > 4 and state(socket_path)[4] == "1", "local voice", timeout=45)
        wait_for(lambda: debug_ready(app_port), "hidden player")

        key_display = display.Display()
        root = key_display.screen().root
        keycode = key_display.keysym_to_keycode(XK.string_to_keysym("r"))
        root.grab_key(keycode, X.Mod4Mask, False, X.GrabModeAsync, X.GrabModeAsync)
        key_display.sync()

        def keys():
            while not stop_keys.is_set():
                if not select.select([key_display.fileno()], [], [], 0.1)[0]:
                    continue
                while key_display.pending_events():
                    event = key_display.next_event()
                    if event.type == X.KeyPress and event.detail == keycode:
                        stamp = time.monotonic()
                        result = subprocess.run([str(ROOT / "scripts/shortcut.sh"), "read"], env=env,
                                                capture_output=True, text=True, timeout=15)
                        key_events.put((stamp, result.returncode))

        key_thread = threading.Thread(target=keys, daemon=True)
        key_thread.start()

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{browser_port}")
            page = browser.contexts[0].pages[0]
            page.wait_for_selector("#sample")
            page.evaluate("document.fonts.ready")
            page.bring_to_front()
            box = page.locator("#sample").bounding_box()
            if not box or box["width"] > 1000:
                raise RuntimeError("The demo sentence does not fit on one line")
            player = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{app_port}").contexts[0].pages[0]

            log = (temp / "ffmpeg.log").open("wb")
            progress = temp / "progress.txt"
            recorder = subprocess.Popen([
                "ffmpeg", "-hide_banner", "-nostdin", "-y", "-f", "x11grab", "-draw_mouse", "1",
                "-video_size", "1280x720", "-framerate", "30", "-i", env["DISPLAY"],
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-threads", "4",
                "-pix_fmt", "yuv420p", "-stats_period", "0.1", "-progress", str(progress),
                str(take / "capture.mp4"),
            ], env=env, stdout=subprocess.DEVNULL, stderr=log, start_new_session=True)
            wait_for(lambda: progress.exists() and "frame=" in progress.read_text(), "screen recording")
            started = time.monotonic()
            rest(0.7)
            x0, x1 = box["x"] - 3, box["x"] + box["width"] + 3
            y = box["y"] + box["height"] / 2
            page.mouse.move(x0, y)
            page.mouse.down()
            for step in range(1, 25):
                page.mouse.move(x0 + (x1 - x0) * step / 24, y)
                rest(0.035)
            page.mouse.up()
            if page.evaluate("window.getSelection().toString()") != SAMPLE:
                raise RuntimeError("The visible sample was not selected exactly")
            if run("xclip", "-out", "-selection", "primary", env=env) != SAMPLE:
                raise RuntimeError("The primary selection does not match the visible sample")
            selection_time = time.monotonic() - started
            rest(0.5)
            run("xdotool", "key", "super+r", env=env)
            def key_event():
                try:
                    return key_events.get_nowait()
                except queue.Empty:
                    return None

            key_time, status = wait_for(key_event, "shortcut", timeout=15)
            if status:
                raise RuntimeError("The selection shortcut failed")
            wait_for(lambda: len(state(socket_path)) > 1 and state(socket_path)[1] == "1", "active speech")
            def visible_window():
                result = subprocess.run(
                    ["xdotool", "search", "--onlyvisible", "--name", "^Read Aloud$"],
                    env=env, capture_output=True, text=True, timeout=10,
                )
                return result.stdout.split()[0] if result.returncode == 0 and result.stdout.strip() else None

            window_id = wait_for(visible_window, "visible player")
            # Xvfb has no window manager to honor the app's always-on-top hint.
            run("xdotool", "windowraise", window_id, env=env)
            player_show = time.monotonic() - started
            speech_event = take / "speech-start.json"
            wait_for(speech_event.exists, "speech playback")
            voice_time = json.loads(speech_event.read_text())["time"] - started

            def linked():
                graph = run("pw-link", "-l")
                return all(f"{player_name}:output_{ch}\n  |-> {sink_name}:playback_{ch}" in graph
                           for ch in ("FL", "FR"))

            wait_for(linked, "speech connected to the isolated sink", timeout=3)
            rest(0.7)
            width = player.evaluate("window.innerWidth")
            speed_button = player.get_by_role("button", name="Speed")
            voice_button = player.get_by_role("button", name="Voice")
            if width != 204 or speed_button.locator("svg.lucide-zap").count() != 1 or voice_button.count() != 1:
                raise RuntimeError("The captured player does not have the current voice and speed controls")

            def save_player_image(name, height):
                if player.evaluate("window.innerHeight") != height:
                    raise RuntimeError("The player did not reach the expected height")
                cdp = player.context.new_cdp_session(player)
                try:
                    cdp.send("Emulation.setDefaultBackgroundColorOverride", {
                        "color": {"r": 0, "g": 0, "b": 0, "a": 0},
                    })
                    shot = cdp.send("Page.captureScreenshot", {
                        "format": "png", "captureBeyondViewport": True,
                        "clip": {"x": 0, "y": 0, "width": width, "height": height, "scale": 3},
                    })
                    (take / name).write_bytes(base64.b64decode(shot["data"]))
                finally:
                    cdp.send("Emulation.setDefaultBackgroundColorOverride")
                    cdp.detach()

            save_player_image("player-bar.png", 40)
            speed = speed_button.bounding_box()
            geometry = dict(line.split("=", 1) for line in run("xdotool", "getwindowgeometry", "--shell", window_id, env=env).splitlines() if "=" in line)
            if int(geometry["WIDTH"]) != width:
                raise RuntimeError("The player window and screenshot have different widths")
            px = int(geometry["X"]) + round(speed["x"] + speed["width"] / 2)
            py = int(geometry["Y"]) + round(speed["y"] + speed["height"] / 2)
            run("xdotool", "mousemove", str(px), str(py), "click", "1", env=env)
            wait_for(lambda: player.get_by_role("menu", name="Speed").count() == 1, "speed menu")
            menu_open = time.monotonic() - started
            save_player_image("player-menu.png", 196)
            rest(1.1)
            run("xdotool", "mousemove", str(px), str(py), "click", "1", env=env)
            wait_for(lambda: player.get_by_role("menu", name="Speed").count() == 0, "speed menu close")
            menu_close = time.monotonic() - started
            wait_for(lambda: len(state(socket_path)) > 1 and state(socket_path)[1] == "0", "speech to finish", timeout=20)
            wait_for(lambda: visible_window() is None, "player to hide")
            player_hide = time.monotonic() - started
            rest(1.0)
            stop(recorder, signal.SIGINT)
            recorder = None
            duration = time.monotonic() - started
            if ui_fingerprint() != ui_before:
                raise RuntimeError("The player changed while the demo was being captured")
            (take / "timing.json").write_text(json.dumps({
                "selection": selection_time, "shortcut": key_time - started,
                "voice": voice_time, "menu_open": menu_open, "menu_close": menu_close,
                "player_show": player_show, "player_hide": player_hide,
                "player": {"x": int(geometry["X"]), "y": int(geometry["Y"]), "width": width},
                "pointer": {"x": px, "y": py}, "duration": duration,
            }, indent=2) + "\n")
            (take / "ui-hashes.json").write_text(json.dumps(ui_before, indent=2) + "\n")
            success = True
            print(f"Captured real selection, shortcut, speech and speed menu: {take}")
    finally:
        stop_keys.set()
        if key_thread is not None:
            key_thread.join(timeout=3)
        if key_display is not None:
            key_display.close()
        if recorder is not None:
            stop(recorder, signal.SIGINT)
        if app is not None:
            try:
                send(temp / "runtime/daemon.sock", "SHUTDOWN")
                app.wait(timeout=8)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
            stop(app)
        stop(chrome)
        if sink is None:
            sink = sink_id(f"read_aloud_demo_{os.getpid()}")
        if sink is not None:
            run("pw-cli", "destroy", str(sink))
        if log is not None:
            log.close()
        subprocess.run(["gio", "trash", str(temp)], check=True)
        if not success:
            subprocess.run(["gio", "trash", str(take)], check=True)


if __name__ == "__main__":
    main()
