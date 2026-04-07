#!/usr/bin/env bash
set -euo pipefail

APP_NAME="serialVerifier"
APP_VERSION="${APP_VERSION:-0.1.0}"

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "dpkg-deb not found. Install the 'dpkg' package and try again."
  exit 1
fi

ARCH="${ARCH:-$(dpkg --print-architecture)}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
fi

./scripts/build_linux_app.sh

STAGE_ROOT="build/deb/${APP_NAME}_${APP_VERSION}_${ARCH}"
DEBIAN_DIR="$STAGE_ROOT/DEBIAN"
BIN_DIR="$STAGE_ROOT/usr/bin"
DESKTOP_DIR="$STAGE_ROOT/usr/share/applications"
ICON_DIR="$STAGE_ROOT/usr/share/icons/hicolor/256x256/apps"

rm -rf "$STAGE_ROOT"
mkdir -p "$DEBIAN_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"

install -m 0755 "dist/$APP_NAME" "$BIN_DIR/$APP_NAME"
install -m 0644 "packaging/linux/serialVerifier.desktop" \
  "$DESKTOP_DIR/serialVerifier.desktop"

"$PYTHON_BIN" - "$STAGE_ROOT" <<'PY'
from __future__ import annotations

from pathlib import Path
import sys

preferred = Path("AIO-ICON-Serial.png")
src_ico = Path("app_icon.ico")
fallback = Path("aio.png")
dst = Path(sys.argv[1]) / "usr/share/icons/hicolor/256x256/apps/serialVerifier.png"

def use_fallback(reason: str) -> None:
    if not fallback.exists():
        print(f"Icon fallback missing: {fallback}. Reason: {reason}")
        return
    dst.write_bytes(fallback.read_bytes())
    print(f"Installed fallback icon from {fallback}")

try:
    from PIL import Image
except Exception as exc:
    use_fallback(f"Pillow not available ({exc})")
    sys.exit(0)

try:
    if preferred.exists():
        img = Image.open(preferred)
    else:
        img = Image.open(src_ico)
    frames = []
    if getattr(img, "n_frames", 1) > 1:
        for i in range(img.n_frames):
            img.seek(i)
            frames.append(img.copy())
        img = max(frames, key=lambda im: im.size[0] * im.size[1])
    img = img.convert("RGBA")
    img = img.resize((256, 256), Image.LANCZOS)
    img.save(dst)
    source = preferred if preferred.exists() else src_ico
    print(f"Installed icon from {source}")
except Exception as exc:
    use_fallback(f"Icon conversion failed ({exc})")
PY

CONTROL_TEMPLATE="packaging/deb/control.in"
CONTROL_OUT="$DEBIAN_DIR/control"
sed -e "s/@VERSION@/$APP_VERSION/g" -e "s/@ARCH@/$ARCH/g" "$CONTROL_TEMPLATE" > "$CONTROL_OUT"
chmod 0644 "$CONTROL_OUT"

dpkg-deb --build "$STAGE_ROOT" "dist/${APP_NAME}_${APP_VERSION}_${ARCH}.deb"
echo "Built dist/${APP_NAME}_${APP_VERSION}_${ARCH}.deb"
