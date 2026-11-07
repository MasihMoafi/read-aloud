#!/usr/bin/env python3
"""Run the real daemon and voice with isolated settings and playback.

The playback command only copies the synthesized WAV. No microphone or
desktop audio device is opened. Run after building to New Volume.
"""
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
import wave

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(os.environ["READ_ALOUD_BUILD"])
ORIGINAL_HOME = Path.home()


def check_heat():
    for name in Path("/sys/class/hwmon").glob("hwmon*/name"):
        if name.read_text().strip() == "coretemp":
            if max(int(p.read_text()) for p in name.parent.glob("temp*_input")) >= 78000:
                raise RuntimeError("CPU reached 78°C; stopping the test")
            return
    raise RuntimeError("CPU temperature unavailable")


def wait_for(predicate, process, label, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        check_heat()
        if process.poll() is not None:
            raise RuntimeError(f"Daemon exited while waiting for {label}")
        result = predicate()
        if result:
            return result
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for {label}")


def send(path, command):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(3)
        client.connect(str(path))
        client.sendall((command + "\n").encode())
        client.shutdown(socket.SHUT_WR)
        return client.recv(1024)


def main():
    temp = Path(tempfile.mkdtemp(prefix="portable-worker-", dir=BUILD))
    daemon = None
    subscription = None
    try:
        bundle = os.environ.get("READ_ALOUD_TEST_BUNDLE")
        app_root = Path(bundle) if bundle else ROOT
        binary = app_root / "build/read-aloud" if bundle else BUILD / "read-aloud"
        for folder in ("home", "bin", "runtime", "config", "cache"):
            (temp / folder).mkdir(mode=0o700)
        player = temp / "bin/pw-play"
        player.write_text('#!/bin/sh\nfor last; do :; done\ncp "$last" "$CAPTURE_WAV"\ntouch "$CAPTURE_WAV.done"\n')
        player.chmod(0o700)
        env = {
            "HOME": str(temp / "home") if bundle else str(ORIGINAL_HOME), "PATH": str(temp / "bin") + ":/usr/bin:/bin",
            "LANG": "C.UTF-8", "READ_ALOUD_ROOT": str(app_root), "READ_ALOUD_RUNTIME": str(temp / "runtime"),
            "XDG_RUNTIME_DIR": str(temp / "runtime"), "XDG_CONFIG_HOME": str(temp / "config"),
            "XDG_CACHE_HOME": str(temp / "cache"), "CAPTURE_WAV": str(temp / "speech.wav"),
            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        }
        if not bundle:
            env.update({
                "READ_ALOUD_PYTHON": str(ORIGINAL_HOME / ".local/share/rustidian/kokoro-venv/bin/python"),
                "READ_ALOUD_MODEL": str(ORIGINAL_HOME / ".cache/hyperframes/tts/models/kokoro-v1.0.onnx"),
                "READ_ALOUD_VOICES": str(ORIGINAL_HOME / ".cache/hyperframes/tts/voices/voices-v1.0.bin"),
                "READ_ALOUD_NVIDIA_LIB_ROOT": str(ORIGINAL_HOME / "miniconda3/lib/python3.13/site-packages/nvidia"),
            })
        with (temp / "daemon.log").open("w") as log:
            daemon = subprocess.Popen([str(binary), "daemon"], env=env, stdout=log,
                                      stderr=subprocess.STDOUT, start_new_session=True)
            socket_path = temp / "runtime/daemon.sock"
            wait_for(socket_path.exists, daemon, "the daemon socket")
            subscription = socket.socket(socket.AF_UNIX)
            subscription.settimeout(0.5)
            subscription.connect(str(socket_path))
            subscription.sendall(b"SUBSCRIBE\n")
            pending = b""
            def ready():
                nonlocal pending
                try:
                    pending += subscription.recv(4096)
                except socket.timeout:
                    return False
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    parts = line.decode().split("\t")
                    if len(parts) > 4 and parts[0] == "STATE" and parts[4] == "1":
                        return True
                return False
            wait_for(ready, daemon, "the configured voice")
            samples = []
            marker = temp / "speech.wav.done"
            for voice in ("af_heart", "bf_emma"):
                subprocess.run(["python3", str(app_root / "worker/voices.py"), "select", voice],
                               env=env, check=True, capture_output=True, text=True)
                if not send(socket_path, "READ\nThis voice uses the configured model.").startswith(b"OK"):
                    raise RuntimeError("The daemon rejected the sample")
                wait_for(marker.exists, daemon, f"speech from {voice}")
                with wave.open(str(temp / "speech.wav"), "rb") as audio:
                    data = audio.readframes(audio.getnframes())
                    if audio.getnframes() < audio.getframerate() // 5 or not any(data):
                        raise RuntimeError(f"{voice} produced no audible samples")
                    samples.append(data)
                marker.rename(temp / f"{voice}.done")
            if samples[0] == samples[1]:
                raise RuntimeError("Choosing another voice did not change the generated speech")
            send(socket_path, "SHUTDOWN")
            daemon.wait(timeout=10)
            source = "bundled" if bundle else "configured"
            print(f"Isolated daemon used the {source} runtime and model; two selected voices produced different speech.")
    except Exception:
        log = temp / "daemon.log"
        if log.exists():
            print(log.read_text()[-4000:])
        raise
    finally:
        if subscription:
            subscription.close()
        if daemon and daemon.poll() is None:
            os.killpg(daemon.pid, signal.SIGTERM)
            daemon.wait(timeout=10)
        subprocess.run(["gio", "trash", str(temp)], check=True)


if __name__ == "__main__":
    main()
