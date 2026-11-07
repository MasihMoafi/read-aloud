# Read Aloud: brief (6 Nov 2026, from Masih via the hackathon session)

## What he wants (his words, then the requirement)
"I select the text that I want and press Windows key + R and it should read it aloud, that's it for now." Like WhisperType (~/Desktop/p/WhisperType, his speech-to-text app), but the reverse: text-to-speech.

1. **Super+R** reads the currently selected text (any app) aloud with local Kokoro on the GPU. The default voice is `af_heart`; Masih can choose another bundled English voice. Pressing Super+R again with a new selection replaces what is playing.
2. **Speed:** steps 1.0 → 1.25 → 1.5 → 1.75 → 2.0. **Super+=** (the +/= key) goes one step faster, **Super+-** one step slower, while playing; the choice is remembered for next time. Changing speed mid-reading continues from the current sentence at the new speed.
3. **Small floating player** appears while reading: play/pause, stop, voice and speed buttons, current speed shown; it goes away when reading ends.
4. English only. Offer the bundled local voices; save the chosen voice. No highlighting in v1. Masih chose local voices first on 7 Nov; other providers are deferred.
5. Stack: **Rust** core + **Electron** player, if they fit together (e.g. a Rust daemon the Electron window talks to over a local socket, or napi-rs). Pick the simpler sound design and say why in the README.
6. Fast: the first sound within about 1 s of the hotkey. Keep the model loaded in a long-lived worker; render the next sentence while the current one plays.

## Facts about this machine (checked 6 Nov)
- GNOME on Wayland (XWayland present). Apps cannot grab global keys: register the three keys as GNOME custom shortcuts (`org.gnome.settings-daemon.plugins.media-keys custom-keybindings`; keep the existing `predict-toggle` entry, Ctrl+Alt+P). Super+R, Super+equal, Super+minus are free; the magnifier uses Alt+Super+=/-.
- Selection: `xclip -o -selection primary` returns the selected text (checked with gnome-terminal). `wl-paste` is not installed.
- Kokoro (kokoro-onnx 0.4.7 + onnxruntime-gpu 1.23.2): Python `~/.local/share/rustidian/kokoro-venv/bin/python`; model `~/.cache/hyperframes/tts/models/kokoro-v1.0.onnx`; voices `~/.cache/hyperframes/tts/voices/voices-v1.0.bin`. CUDA works only with `LD_LIBRARY_PATH` set to every `~/miniconda3/lib/python3.13/site-packages/nvidia/*/lib` and `ONNX_PROVIDER=CUDAExecutionProvider`: then ~0.3 s per sentence (CPU ~1 s); cold load ~5 s. Kokoro's `create(..., speed=)` takes the speed. GPU: RTX 3070 Laptop, 8 GB. Elpis's worker (`~/Desktop/p/Elpis/apps/elpis-desktop/bridge/kokoro-worker.py`) shows the request/reply pattern.
- Audio: `pw-play` (PipeWire).
- An earlier stopgap exists: `~/.local/bin/claude-tts` (Claude Code `/tts`). Leave it alone.

## Rules
- Read `~/Desktop/p/skills/dev/AGENTS.md` and `REQUIREMENTS.md` first and follow them (verify as he would use it; replies short, answer last; leave nothing running).
- Machine: one heavy job at a time, `nice -n 19`; Rust build output on the New Volume (`udisksctl mount -b /dev/nvme0n1p3 --no-user-interaction`, `/run/media/masih/New Volume`), never on `/`. Check `free -h` first.
- Ask before any download (npm/cargo packages included); network routing per `~/Desktop/p/skills/workstation/SKILL.md`.
- Project docs per `~/Desktop/p/skills/project-docs/SKILL.md` (AGENTS.md, ES.md); git repo in this folder; add one line for it in `~/Desktop/p/lat.md/workspace.md`.
- Done = Masih selects text in a terminal and in Chromium, presses Super+R and hears it within ~1 s; Super+= / Super+- change speed audibly; the player shows and hides. Verify each yourself before telling him.
