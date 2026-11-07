# Read Aloud

Select English text and press **Super+R** (Windows key + R) to
hear it. Select new text and press it again to replace speech.

While it reads, **Super+=** and **Super+-** change the speed.
The small floating player has pause, stop, and a speed menu.
The voice button offers the bundled English voices; the chosen
voice and speed are saved. Already buffered speech can finish in
the previous voice after a change.

Open Read Aloud from the app launcher to see the shortcut.
Close that window when you are done; the app stays ready.
The app also starts at login and keeps the voice ready. If it
was not running, the first shortcut starts it; loading the
model can take several seconds. Later requests use the warm
model. A preferred output is used while connected; otherwise
the app uses the system output.

## Installation

CI is configured to produce three x86-64 artifacts for Ubuntu 24.04 and later:
`read-aloud-deb`, `read-aloud-appimage`, and `read-aloud-snap`. Download and
extract one workflow artifact before using the commands below. These packages
have not yet been tested on a clean machine.

For the deb, install its dependencies with apt:

```sh
sudo apt install ./read-aloud-0.1.0-amd64.deb
```

For the AppImage, install `xclip`, `pipewire-bin`, and `libfuse2t64`, then make
the downloaded AppImage executable and run it:

```sh
sudo apt install xclip pipewire-bin libfuse2t64
chmod +x read-aloud-0.1.0-x86_64.AppImage
./read-aloud-0.1.0-x86_64.AppImage --show
```

For the unsigned development snap, install it locally and connect PipeWire:

```sh
sudo snap install --dangerous ./read-aloud_0.1.0_amd64.snap
sudo snap connect read-aloud:pipewire
```

Open the deb or snap from the launcher, or run the AppImage. On first run it downloads about 337 MiB of
voice files, verifies them, and stores them in your user data; the snap uses
`$SNAP_USER_COMMON`. Internet access is needed for this download. The deb and
AppImage register three GNOME shortcuts and login startup on first run. The
AppImage must remain at the same path for these entries to work.

The strict snap does not register host shortcuts or login startup. In GNOME
Settings, add custom shortcuts for Super+R, Super+=, and Super+- with these
respective commands: `read-aloud --shortcut read`, `read-aloud --shortcut
faster`, and `read-aloud --shortcut slower`.

To remove the deb or AppImage's shortcuts and login entry, run the installed
app with `--uninstall-setup` before removing the package or file. Remove the
snap with `sudo snap remove read-aloud` and remove its custom GNOME shortcuts
in Settings. Model files remain in user data unless you remove them.

See [third-party notices](THIRD_PARTY_NOTICES.md) for licences and the
remaining source audit.

## Design

The Rust process owns playback, speed, and sentence
prefetching. It keeps a Python Kokoro worker loaded and
streams each rendered sentence through PipeWire. Electron
connects to it over a private local socket. This avoids a
native Node bridge and keeps the voice running while the
player is hidden.

The development launcher stores `app.log` in the `read-aloud` folder under
`~/.cache`.
