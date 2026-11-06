# SPEC: Read Aloud

Goal: Read selected English text on GNOME with a shortcut and a small player.

Constraints: Follow [BRIEF.md](BRIEF.md); reuse installed software without downloading. Keep synthesis local on CUDA and build output on New Volume.

Statuses describe offscreen checks; Masih's own desktop check remains open.

| # | Item | Acceptance check | Status |
| --- | --- | --- | --- |
| 1 | Selection and replacement | Select text in terminal and Chromium, press Super+R, and hear it; selecting other text and pressing again replaces it. | offscreen checked |
| 2 | Latency and prefetch | With the model ready, measure hotkey to first sound near one second; subsequent sentences play without waiting for synthesis. | offscreen checked |
| 3 | Speed | Super+= and Super+- change the current sentence through five steps; the setting survives restart. | offscreen checked |
| 4 | Player | Play/pause, stop, and the five-step speed slider work; the player appears during reading and hides afterward. | offscreen checked |
| 5 | Failure | Empty selections and worker/audio errors do not leave a false playing state; errors reach the player. | offscreen checked |
| 6 | Concurrency | A new selection or speed change discards obsolete audio even when synthesis is in progress. | offscreen checked |
| 7 | Observability | A local log identifies worker readiness and errors without recording selected text. | offscreen checked |
| 8 | Rollback | Uninstall removes this app's shortcuts and startup entry while preserving other shortcuts. | checked |

Plan: A Rust daemon coordinates a resident Python Kokoro worker and PipeWire playback. An Electron window connects over a private local socket. GNOME shortcuts invoke a small client of the same Rust binary. This keeps the GPU model loaded and isolates playback from the UI.

| Task | Importance | Difficulty | Done check |
| --- | --- | --- | --- |
| Implement the worker and Rust daemon | foundational | hard | A selected sentence reaches PipeWire and can be replaced. |
| Add the player | important | medium | Its controls reflect and change daemon state. |
| Register startup and shortcuts | important | medium | All three bindings work and uninstall preserves the existing binding. |
| Verify on GNOME | foundational | hard | All checks above pass using the real desktop and audio. |

Non-goals: voice selection, highlighting, translation, and network services.
