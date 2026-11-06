#!/usr/bin/env python3
"""Exercise real Kokoro and PipeWire on an isolated sink; no desktop input."""

import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import tempfile
import time

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(os.environ.get("READ_ALOUD_BUILD", "/run/media/masih/New Volume/dev/read-aloud"))
WORK = Path.home() / "Work/tries"
SINK = f"read-aloud-check-{os.getpid()}"


def command(*args):
    return subprocess.run(args, text=True, capture_output=True, check=True).stdout


def send(path, name, text=""):
    with socket.socket(socket.AF_UNIX) as client:
        client.connect(str(path))
        client.sendall((name + "\n" + text).encode())
        client.shutdown(socket.SHUT_WR)
        reply = client.recv(1024)
        if not reply.startswith(b"OK"):
            raise AssertionError(reply)


class States:
    def __init__(self, path):
        self.client = socket.socket(socket.AF_UNIX)
        self.client.connect(str(path))
        self.client.sendall(b"SUBSCRIBE\n")
        self.pending = b""

    def wait(self, predicate, timeout=15, allow_error=False):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if b"\n" not in self.pending:
                self.client.settimeout(max(.01, deadline - time.monotonic()))
                chunk = self.client.recv(4096)
                if not chunk:
                    raise AssertionError("Speech service disconnected")
                self.pending += chunk
            while b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                state = line.decode().split("\t")
                if len(state) >= 6 and state[5] and not allow_error:
                    raise AssertionError(state[5])
                if state[0] == "STATE" and predicate(state):
                    return state
        raise AssertionError("Timed out waiting for player state")

    def close(self):
        self.client.close()


def sink_id():
    listing = command("pw-cli", "ls", "Node")
    for block in re.split(r"(?=\n\s*id \d+, type PipeWire:Interface:Node)", listing):
        if f'node.name = "{SINK}"' in block:
            return re.search(r"\bid (\d+),", block).group(1)
    raise AssertionError("PipeWire test sink did not appear")


def wait_socket(path, process):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("Speech service exited during startup")
        if path.exists():
            return
        time.sleep(.05)
    raise AssertionError("Speech service socket did not appear")


def capture(states, socket_path, output):
    recorder_name = SINK + "-recorder"
    recorder = subprocess.Popen(
        ["pw-record", "--target", "0", "--properties", f"{{ node.name = {recorder_name} }}", "--rate", "48000", "--channels", "2", str(output)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            ports = command("pw-link", "-i")
            if all(f"{recorder_name}:input_{channel}" in ports for channel in ("FL", "FR")):
                break
            if recorder.poll() is not None:
                raise AssertionError("Recorder exited before its ports appeared")
            time.sleep(.05)
        else:
            raise AssertionError("Recorder ports did not appear")
        for channel in ("FL", "FR"):
            command("pw-link", f"{SINK}:monitor_{channel}", f"{recorder_name}:input_{channel}")
        graph = command("pw-link", "-l")
        for channel in ("FL", "FR"):
            block = re.search(rf"(?m)^{re.escape(recorder_name)}:input_{channel}\n((?:\s+\|<- [^\n]+\n)*)", graph)
            sources = re.findall(r"\|<- ([^\n]+)", block.group(1)) if block else []
            if sources != [f"{SINK}:monitor_{channel}"]:
                raise AssertionError(f"Unsafe recorder links: {sources}")
        time.sleep(.2)
        send(socket_path, "PAUSE")
        states.wait(lambda state: state[1] == "0", timeout=30)
        time.sleep(.2)
    finally:
        if recorder.poll() is None:
            os.killpg(recorder.pid, signal.SIGINT)
        recorder.communicate(timeout=5)
    samples, rate = sf.read(output)
    active = np.flatnonzero(np.max(np.abs(samples), axis=1) > .01)
    if len(active) < rate // 10:
        raise AssertionError("No speech reached the PipeWire sink")
    return (active[-1] - active[0]) / rate


def prepare(states, socket_path, text, speed):
    send(socket_path, "READ", text)
    states.wait(lambda state: state[1] == "1")
    send(socket_path, "PAUSE")
    state = states.wait(lambda state: state[1] == "1" and state[2] == "1")
    if int(state[3]) != speed:
        send(socket_path, f"SPEED {speed}")
        states.wait(lambda state: state[2] == "1" and int(state[3]) == speed)


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix="read-aloud-test-", dir=WORK))
    sink = None
    daemon = None
    states = None
    log = None
    try:
        command("pw-cli", "create-node", "adapter", f'{{ factory.name = support.null-audio-sink node.name = "{SINK}" media.class = Audio/Sink audio.position = [ FL FR ] object.linger = true priority.session = 1 }}')
        sink = sink_id()
        bin_dir = temp / "bin"
        bin_dir.mkdir()
        player = bin_dir / "pw-play"
        player.write_text(f'#!/bin/sh\nexec /usr/bin/pw-play --target "{SINK}" "$@"\n')
        player.chmod(0o755)
        env = os.environ.copy()
        env.update({"READ_ALOUD_ROOT": str(ROOT), "READ_ALOUD_RUNTIME": str(temp / "runtime"), "XDG_CONFIG_HOME": str(temp / "config"), "PATH": str(bin_dir) + os.pathsep + env["PATH"]})
        log = (temp / "daemon.log").open("wb")

        def start():
            process = subprocess.Popen([str(BUILD / "read-aloud"), "daemon"], env=env, stdout=log, stderr=log, start_new_session=True)
            wait_socket(temp / "runtime/daemon.sock", process)
            return process

        daemon = start()
        socket_path = temp / "runtime/daemon.sock"
        states = States(socket_path)
        states.wait(lambda state: state[4] == "1")
        private_text = "Private selection must never appear in the error log."
        (temp / "runtime").chmod(0o500)
        try:
            send(socket_path, "READ", private_text)
            failed = states.wait(lambda state: len(state) >= 6 and bool(state[5]), allow_error=True)
            if failed[1] != "0":
                raise AssertionError("A failed render left playback active")
        finally:
            (temp / "runtime").chmod(0o700)
        log.flush()
        if private_text in (temp / "daemon.log").read_text(errors="replace"):
            raise AssertionError("Selected text appeared in the log")
        send(socket_path, "READ", " \t\n")
        empty_check = States(socket_path)
        try:
            empty = empty_check.wait(lambda state: True, allow_error=True)
            if empty[1] != "0":
                raise AssertionError("An empty selection started playback")
        finally:
            empty_check.close()
        text = "This sentence is read aloud so we can compare the sound at both speeds."
        prepare(states, socket_path, text, 0)
        normal = capture(states, socket_path, temp / "normal.wav")
        prepare(states, socket_path, text, 4)
        faster = capture(states, socket_path, temp / "faster.wav")
        if faster >= normal * .75:
            raise AssertionError(f"2x speech was not shorter: {normal:.2f}s versus {faster:.2f}s")

        send(socket_path, "READ", "This longer sentence is immediately replaced and must not continue playing afterward.")
        send(socket_path, "READ", "New selection.")
        states.wait(lambda state: state[1] == "1")
        send(socket_path, "PAUSE")
        states.wait(lambda state: state[2] == "1")
        replacement = capture(states, socket_path, temp / "replacement.wav")
        if replacement >= 2:
            raise AssertionError(f"An obsolete selection played: {replacement:.2f}s")

        player.write_text("#!/bin/sh\nexit 1\n")
        send(socket_path, "READ", "Audio failure test.")
        failure = states.wait(lambda state: len(state) >= 6 and bool(state[5]), allow_error=True)
        if failure[1] != "0":
            raise AssertionError("An audio failure left playback active")

        states.close()
        states = None
        send(socket_path, "SHUTDOWN")
        daemon.wait(timeout=5)
        daemon = start()
        states = States(socket_path)
        restored = states.wait(lambda state: True)
        if restored[3] != "4":
            raise AssertionError("Speed did not survive restart")
        children = Path(f"/proc/{daemon.pid}/task/{daemon.pid}/children").read_text().split()
        if len(children) != 1:
            raise AssertionError("Speech worker was not started")
        os.kill(int(children[0]), signal.SIGKILL)
        if daemon.wait(timeout=5) == 0 or socket_path.exists():
            raise AssertionError("Worker failure left the service running")
        print(f"Audio: {normal:.2f}s at 1x, {faster:.2f}s at 2x; replacement: {replacement:.2f}s; speed restored; empty selection and failures handled without logging text.")
    finally:
        if states is not None:
            states.close()
        if daemon is not None and daemon.poll() is None:
            try:
                send(temp / "runtime/daemon.sock", "SHUTDOWN")
                daemon.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                os.killpg(daemon.pid, signal.SIGTERM)
                daemon.wait(timeout=5)
        if log is not None:
            log.close()
        if sink is None:
            try:
                sink = sink_id()
            except (AssertionError, subprocess.CalledProcessError):
                pass
        if sink is not None:
            command("pw-cli", "destroy", sink)
        subprocess.run(["gio", "trash", str(temp)], check=True)


if __name__ == "__main__":
    main()
