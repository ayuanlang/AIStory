#!/usr/bin/env bash
# Unpack official Blender into backend/.blender for Render's Debian image.
# apt installs do not survive into the native runtime, so missing X11/GL
# libraries are copied next to the binary and found via LD_LIBRARY_PATH.
set -euo pipefail

if [ "$(uname -s)" != "Linux" ]; then
  echo "[blender] skip: not Linux"
  exit 0
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/.blender"
VERSION="4.2.16"
URL="https://download.blender.org/release/Blender4.2/blender-${VERSION}-linux-x64.tar.xz"
PKGS="libx11-6 libxext6 libxi6 libxfixes3 libxrender1 libxxf86vm1 libxt6 libsm6 libice6 libxkbcommon0 libgl1 libglvnd0 libglx0 libdrm2 libxcb1 libxau6 libxdmcp6 libx11-xcb1 libuuid1 libbsd0 libmd0"

TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

echo "[blender] downloading $URL"
curl -fsSL "$URL" -o "$TMP/blender.tar.xz"
mkdir -p "$TMP/extract"
python - "$TMP/blender.tar.xz" "$TMP/extract" <<'PY'
import os
import sys
import tarfile

os.makedirs(sys.argv[2], exist_ok=True)
kwargs = {}
if hasattr(tarfile, "data_filter"):
    kwargs["filter"] = "data"
with tarfile.open(sys.argv[1], "r:xz") as archive:
    archive.extractall(sys.argv[2], **kwargs)
PY

SRC="$(find "$TMP/extract" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [ -z "$SRC" ] || [ ! -f "$SRC/blender" ]; then
  echo "[blender] archive has no blender binary"
  exit 1
fi
rm -rf "$DEST"
mv "$SRC" "$DEST"
chmod +x "$DEST/blender"
if [ -f "$DEST/blender-launcher" ]; then
  chmod +x "$DEST/blender-launcher"
fi

LIB="$DEST/lib"
mkdir -p "$LIB"
export LD_LIBRARY_PATH="$LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

echo "[blender] fetching shared libraries"
mkdir -p "$TMP/debs" "$TMP/broot"
(
  cd "$TMP/debs"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get download $PKGS
)
for deb in "$TMP/debs"/*.deb; do
  dpkg-deb -x "$deb" "$TMP/broot"
done

copy_soname() {
  local name="$1"
  local match target dir current i
  match="$(find "$TMP/broot" -name "$name" | head -n 1)"
  if [ -z "$match" ]; then
    echo "[blender] package tree has no $name"
    return 1
  fi
  cp -a "$match" "$LIB/"
  current="$match"
  for i in 1 2 3 4; do
    if [ -L "$current" ]; then
      target="$(readlink "$current")"
      dir="$(dirname "$current")"
      if [ -e "$dir/$target" ]; then
        cp -a "$dir/$target" "$LIB/"
        current="$dir/$target"
      else
        break
      fi
    else
      break
    fi
  done
}

round=0
while [ "$round" -lt 8 ]; do
  round=$((round + 1))
  mapfile -t missing < <(ldd "$DEST/blender" | awk '/not found/ {print $1}')
  if [ "${#missing[@]}" -eq 0 ]; then
    break
  fi
  echo "[blender] missing: ${missing[*]}"
  progress=0
  for name in "${missing[@]}"; do
    if copy_soname "$name"; then
      progress=1
    fi
  done
  if [ "$progress" -eq 0 ]; then
    echo "[blender] could not supply: ${missing[*]}"
    ldd "$DEST/blender" || true
    exit 1
  fi
done

echo "[blender] $( "$DEST/blender" --background --version | head -n 1 )"
echo "[blender] installed at $DEST"
