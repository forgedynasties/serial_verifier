#!/usr/bin/env bash
set -euo pipefail

SRC="${1:-AIO-ICON-Serial.png}"
OUT="${2:-app_icon.ico}"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

if [ ! -f "$SRC" ]; then
  echo "Missing source icon: $SRC" >&2
  exit 1
fi

"$PYTHON_BIN" - <<'PY' "$SRC" "$OUT"
from __future__ import annotations

from pathlib import Path
import sys

src = Path(sys.argv[1])
out = Path(sys.argv[2])

try:
    from PIL import Image
except Exception as exc:
    raise SystemExit(f"Pillow is required for icon conversion: {exc}")

img = Image.open(src).convert("RGBA")
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
img.save(out, format="ICO", sizes=sizes)
print(f"Wrote {out}")
PY
