# Read Aloud

Select English text and press **Super+R** (Windows key + R) to
hear it. Select new text and press it again to replace speech.

While it reads, **Super+=** and **Super+-** change the speed.
The floating player also has pause, stop, and a faster button.
The chosen speed is saved for next time.

Open Read Aloud from the app launcher to see the shortcut.
Close that window when you are done; the app stays ready.
The app also starts at login and keeps the voice ready. If it
was not running, the first shortcut starts it; loading the
model can take several seconds. Later requests use the warm
model. A preferred output is used while connected; otherwise
the app uses the system output.

## Setup

This machine already has the Kokoro model, CUDA libraries,
PipeWire, and the packages used to build the player. No
download is needed for the following commands:

```sh
scripts/build.sh
python3 scripts/setup.py install
```

The build and its copy of Electron live on New Volume. The
setup script adds three GNOME shortcuts, a launcher, and a
login entry; it preserves other custom shortcuts. To remove
them and stop the app, run `python3 scripts/setup.py uninstall`.

The build reuses the Electron installation in `clocki` and
the UI packages in `svg`. The resident voice uses the
`rustidian` Kokoro environment and the cached model and
voices named in [BRIEF.md](BRIEF.md).

## Design

The Rust process owns playback, speed, and sentence
prefetching. It keeps a Python Kokoro worker loaded and
streams each rendered sentence through PipeWire. Electron
connects to it over a private local socket. This avoids a
native Node bridge and keeps the voice running while the
player is hidden.

The app stores `app.log` in the `read-aloud` folder under
`~/.cache`. It records timings and errors, not selected text.
The focused audio integration check is:

```sh
nice -n 19 ~/.local/share/rustidian/kokoro-venv/bin/python tests/speech_integration.py
```
