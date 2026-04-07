#!/usr/bin/env bash
set -euo pipefail

APP_NAME="serialVerifier"
BIN_PATH="dist/$APP_NAME"
DESKTOP_SRC="packaging/linux/serialVerifier.desktop"

if [ ! -f "$BIN_PATH" ]; then
  echo "Missing $BIN_PATH. Run scripts/build_linux_app.sh first."
  exit 1
fi

install -D -m 0755 "$BIN_PATH" "$HOME/.local/bin/$APP_NAME"
install -D -m 0644 "$DESKTOP_SRC" "$HOME/.local/share/applications/serialVerifier.desktop"

ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_DST="$ICON_DIR/$APP_NAME.png"
mkdir -p "$ICON_DIR"

python3 - <<'PY'
from __future__ import annotations

from pathlib import Path
import sys

src = Path("app_icon.ico")
fallback = Path("aio.png")
dst = Path.home() / ".local/share/icons/hicolor/256x256/apps/serialVerifier.png"

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
    img = Image.open(src)
    frames = []
    if getattr(img, "n_frames", 1) > 1:
        for i in range(img.n_frames):
            img.seek(i)
            frames.append(img.copy())
        img = max(frames, key=lambda im: im.size[0] * im.size[1])
    img = img.convert("RGBA")
    img = img.resize((256, 256), Image.LANCZOS)
    img.save(dst)
    print(f"Installed icon from {src}")
except Exception as exc:
    use_fallback(f"Icon conversion failed ({exc})")
PY

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
fi

echo "Installed. If the launcher doesn't appear, log out/in or restart the shell."
