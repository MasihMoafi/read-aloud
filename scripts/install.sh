#!/usr/bin/env bash
# install.sh: one command installs Read Aloud from the latest release.
#   curl -fsSL https://raw.githubusercontent.com/MasihMoafi/read-aloud/main/scripts/install.sh | bash
# Ubuntu and Debian (x86_64): the .deb through apt (asks for your password); its SHA-256 is checked first.
#   READ_ALOUD_RELEASE_VERSION=v0.1.0  a fixed release instead of the latest
#   READ_ALOUD_DEB=/path/to/file.deb   install this local package instead of downloading (used by CI)
set -euo pipefail
[[ "$(uname -s)-$(uname -m)" == Linux-x86_64 ]] || { echo "Read Aloud publishes Linux x86_64 only (this is $(uname -s)-$(uname -m))." >&2; exit 1; }
command -v apt-get >/dev/null || { echo "Read Aloud is packaged for Ubuntu and Debian (apt) only for now." >&2; exit 1; }
sudo_() { if [[ $(id -u) == 0 ]]; then "$@"; else sudo "$@"; fi; }

work=$(mktemp -d "${TMPDIR:-/tmp}/read-aloud-install.XXXXXX"); trap 'rm -rf "$work"' EXIT
if [[ -n ${READ_ALOUD_DEB:-} ]]; then
  deb=$READ_ALOUD_DEB
else
  repository=${READ_ALOUD_GITHUB_REPOSITORY:-MasihMoafi/read-aloud}
  tag=${READ_ALOUD_RELEASE_VERSION:-$(curl -fsSI "https://github.com/$repository/releases/latest" | tr -d '\r' | sed -n 's#^[Ll]ocation: .*/tag/##p')}
  [[ $tag == v* ]] || { echo "Could not find the latest Read Aloud release." >&2; exit 1; }
  file="read-aloud-${tag#v}-amd64.deb"; release="https://github.com/$repository/releases/download/$tag"
  curl -fL --progress-bar "$release/$file" -o "$work/$file"
  curl -fsSL "$release/$file.sha256" -o "$work/$file.sha256"
  (cd "$work" && sha256sum -c --quiet "$file.sha256")
  deb="$work/$file"
fi

echo "Installing Read Aloud with apt…"
sudo_ env DEBIAN_FRONTEND=noninteractive apt-get install -y "$(realpath "$deb")"
echo "Done. Open Read Aloud from your app menu once; then select English text anywhere and press Super+R."
echo "The voice (337 MB) downloads the first time Read Aloud starts. Remove it with: sudo apt remove read-aloud"
