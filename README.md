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

On Ubuntu 24.04 or later, or Debian (x86-64):

```sh
curl -fsSL https://raw.githubusercontent.com/MasihMoafi/read-aloud/main/scripts/install.sh | bash
```

Then open Read Aloud from your app menu once. The first start downloads the voice (about 337 MiB, checked), sets
up the Super+R, Super+= and Super+- shortcuts in GNOME, and starts Read Aloud at login.

<details>
<summary>Install the .deb by hand, or remove Read Aloud</summary>

Download `read-aloud-<version>-amd64.deb` and its `.sha256` from the
[latest release](https://github.com/MasihMoafi/read-aloud/releases/latest), then:

```sh
sha256sum -c read-aloud-*-amd64.deb.sha256
sudo apt install ./read-aloud-*-amd64.deb
```

To remove it, first run `read-aloud --uninstall-setup` (removes the shortcuts and login entry), then
`sudo apt remove read-aloud`. The voice files stay in your user data until you delete them.

</details>

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
