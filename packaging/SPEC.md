# Distribution acceptance checks

Goal: Install Read Aloud on another Linux user's machine without CUDA or bundled model files.

| # | Acceptance check | Status |
| --- | --- | --- |
| 1 | CPU-only packages start the player, speech worker and GNOME shortcuts without machine-specific paths. | todo |
| 2 | First run visibly downloads the pinned model and voices to user data, verifies SHA-256 and starts speech only after both pass. | todo |
| 3 | Offline, interrupted and checksum-failed downloads show an actionable failure and leave no trusted partial file; retry succeeds. | todo |
| 4 | Concurrent starts cannot expose partially written files; an existing valid download works offline. | todo |
| 5 | CI builds strict core24 Snap, deb and AppImage without model, voices or NVIDIA libraries. | todo |
| 6 | Packages carry complete third-party notices and required corresponding source; clean-user install and uninstall work. | todo |
| 7 | An earlier release remains installable as rollback; no release is published by this branch. | todo |

Plan: establish verified model acquisition, integrate it with player startup and a CPU runtime, then build and inspect each package in CI. Verify the player and speech in a clean user session before claiming installation works.
