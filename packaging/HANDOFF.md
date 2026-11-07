# Distribution handoff

Goal: Ship Read Aloud independently as a small CPU-only Snap, deb and AppImage.

Done in this branch:
- The worker and daemon request and recognize the CPU ONNX provider. A bundled Python interpreter or `READ_ALOUD_PYTHON` can replace the developer's local interpreter.
- `electron/model-download.ts` verifies pinned v1.0 model and voice hashes, streams to private temporary files, and atomically moves verified files into place. Its focused tests exercise checksum failure, interruption, offline operation, retry and reuse of valid files.

Still required:
1. Bundle the TypeScript downloader for Electron. Connect first-run progress, failure and retry to the player; keep the daemon stopped until both files pass verification. Set `READ_ALOUD_MODEL` and `READ_ALOUD_VOICES` to user data paths, using `SNAP_USER_COMMON` for Snap. Check multiple launches and interrupted downloads in the real player.
2. Build a relocatable CPU-only Python runtime and supply its licences and corresponding source, including eSpeak NG. Remove developer-only paths from the packaged startup, shortcut and UI build. Preserve selection, shortcuts, autostart and uninstall behavior.
3. Add the strict core24 Snap and electron-builder deb/AppImage configuration and a CI workflow. Build on CI, inspect the exact artifacts for NVIDIA and model files, measure their sizes and test installation, playback and uninstall in clean GNOME Wayland and on a separate machine.
4. Complete README installation instructions and third-party notices from the actual dependency closure. Resolve the release gates in the launch-prep worktree and Matilda's launch plan before offering a release.

Evidence and limits: `node --test tests/model-download.test.ts` uses simulated HTTP responses and real filesystem writes; the sandbox denies network sockets. The worker was not built or run, and no package was built or installed. The model and voice hashes match the cached local files. The workspace pointer check reports existing cross-project issues and missing worktree agent-doc links; it could not be repaired within the allowed writable paths.

No repo, store name, push, release or upload was created. Masih must approve publication and the specific repo/store actions before they happen.
