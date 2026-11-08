<div align="center">

<img src="assets/logo.svg" width="128" height="128" alt="Read Aloud logo, a teal mockingbird">

# Read Aloud

### Your text, out loud.<br>Select text anywhere on Linux and press Super+R.

[![Latest release](https://img.shields.io/github/v/release/MasihMoafi/read-aloud?style=flat-square&color=147d78&label=release)](https://github.com/MasihMoafi/read-aloud/releases/latest)
[![Linux](https://img.shields.io/badge/Linux-x86__64-147d78?style=flat-square&logo=linux&logoColor=white)](#install)
[![Voice](https://img.shields.io/badge/voice-Kokoro,_on_your_computer-555?style=flat-square)](https://github.com/thewh1teagle/kokoro-onnx)
[![MIT license](https://img.shields.io/badge/license-MIT-555?style=flat-square)](LICENSE)

<a href="#install"><img src="https://img.shields.io/badge/Install-Ubuntu_24.04+_·_Debian-147d78?style=for-the-badge&logo=ubuntu&logoColor=white" alt="Install"></a>

<sub>Beta · v0.1.1 · Linux x86_64, GNOME</sub>

</div>

<br>

https://github.com/user-attachments/assets/da2c0997-1951-4d3c-a876-9e5404f4a163

<p align="center"><sub>Select a passage, press Super+R, listen while you work. Turn the sound on.</sub></p>

## What it does

<table>
<tr>
<td width="33%" valign="top"><b>⌨️ One shortcut</b><br>Select English text in any app and press <b>Super+R</b>. Select new text and press it again to switch.</td>
<td width="33%" valign="top"><b>⏩ Your pace</b><br><b>Super+=</b> and <b>Super+-</b> change the speed while it reads, from normal to 2×.</td>
<td width="33%" valign="top"><b>🎛️ A small player</b><br>Pause, stop, a speed menu and the bundled English voices. Your voice and speed are saved.</td>
</tr>
<tr>
<td valign="top"><b>💻 Voice on your computer</b><br>Kokoro speaks on your CPU; your text is not sent anywhere. The voice downloads once (about 337 MiB, checked).</td>
<td valign="top"><b>🪶 Light when idle</b><br>Keeps the voice loaded for 30 idle minutes, then quits and frees its memory. Closing it quits too; Super+R starts it again.</td>
<td valign="top"><b>🎧 Your headphones</b><br>Plays on your preferred output while it is connected, otherwise on the system output.</td>
</tr>
</table>

## Install

On Ubuntu 24.04 or later, or Debian (x86-64):

```sh
curl -fsSL https://raw.githubusercontent.com/MasihMoafi/read-aloud/main/scripts/install.sh | bash
```

Then open Read Aloud from your app menu once. The first start downloads the voice, sets up the Super+R, Super+=
and Super+- shortcuts in GNOME, and starts Read Aloud at login.

<details>
<summary><b>Install the .deb by hand, or remove Read Aloud</b></summary>

Download `read-aloud-<version>-amd64.deb` and its `.sha256` from the
[latest release](https://github.com/MasihMoafi/read-aloud/releases/latest), then:

```sh
sha256sum -c read-aloud-*-amd64.deb.sha256
sudo apt install ./read-aloud-*-amd64.deb
```

To remove it, first run `read-aloud --uninstall-setup` (removes the shortcuts and login entry), then
`sudo apt remove read-aloud`. The voice files stay in your user data until you delete them.

</details>

<details>
<summary><b>How it works</b></summary>

A Rust process owns playback, speed and sentence prefetching. It keeps a Python Kokoro worker loaded and streams
each rendered sentence through PipeWire. The Electron player connects to it over a private local socket, so the
voice keeps running while the player is hidden. The development launcher writes `app.log` to `~/.cache/read-aloud`.

</details>

## Status

Tested on GitHub's servers: each release installs, starts and uninstalls in a clean Ubuntu 24.04 system. A Snap is
on the way. Report what broke in [Issues](https://github.com/MasihMoafi/read-aloud/issues).

<div align="center"><sub><a href="LICENSE">MIT license</a> · <a href="THIRD_PARTY_NOTICES.md">Third-party notices</a> (Kokoro, eSpeak NG and the other bundled parts keep their own licences)</sub></div>

<!-- more-projects:start -->
## More projects

- [Elpis](https://github.com/MasihMoafi/Elpis): a coding agent for the terminal and desktop, with explicit context control
- [Rustidian](https://github.com/MasihMoafi/rustidian): a native Markdown notebook for Linux that opens Obsidian-format vaults
- [rag-mcp](https://github.com/MasihMoafi/rag-mcp): local hybrid search over your documents, as a CLI and MCP server
- [Skills](https://github.com/MasihMoafi/skills): SKILL.md workflows for coding agents
- [WhisperType](https://github.com/MasihMoafi/WhisperType): local voice input for developers
- [Love Spot](https://github.com/MasihMoafi/love-spot): a shared drawing board where characters talk, draw and compete with you
- [SVG Studio](https://svg.masihmoafi.com): high-quality image vectorization
- [Pin](https://github.com/MasihMoafi/pin): an always-on-top priority note, saved as plain Markdown
- [Clocki](https://github.com/MasihMoafi/clocki): a floating desktop timer for tracking focus hours

All of them: [masihmoafi.com](https://masihmoafi.com/projects)
<!-- more-projects:end -->
