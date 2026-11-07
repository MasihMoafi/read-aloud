# Distribution handoff

## Goal

Produce CPU-only deb, AppImage and strict core24 Snap artifacts for Ubuntu
24.04+ x86-64, with model files downloaded and verified on first run.

## Current state

- Parts 1–2 added the CPU worker, downloader and player download/retry states.
  The player integration has not been exercised in Electron.
- Part 3 adds the Cargo manifest, standalone Python runtime assembly,
  electron-builder configuration, Snap recipe, CI, desktop setup and notices.
  All changes are uncommitted. No builds, pushes, uploads or releases were run.
- The Snap uses the manually connected `pipewire` interface and requires manual
  GNOME shortcuts; it does not register host login startup. The deb and AppImage
  attempt GNOME setup on first launch. These paths have not been tested live.
- The notice file is an index, not a complete dependency and corresponding
  source audit. In particular, verify the exact eSpeak NG binary and source.

## Evidence

Downloader unit test, TypeScript check, `cargo fmt --check`, Python compile,
YAML parsing, shell syntax, logo/contrast check and `git diff --check` passed.
`actionlint` is not installed. The workspace pointer check reports pre-existing
cross-project errors and missing worktree agent-doc links. Direct npm access is
blocked by this session's network sandbox, so new build dependencies were not
installed here. No package, worker or clean-session playback was tested.

## Next action

After the user authorizes the necessary Git operations, run the first CI build.
Inspect all three artifacts and their sizes, then test clean install, first
and offline downloads, retry, playback, selection, shortcuts, login and
uninstall in GNOME Wayland. Complete the licence/source audit before distribution.
Do not claim the acceptance checks in [SPEC.md](SPEC.md) are complete until
those tests pass.
