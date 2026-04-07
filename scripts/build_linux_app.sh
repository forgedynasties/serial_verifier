#!/usr/bin/env bash
set -euo pipefail

APP_NAME="serialVerifier"
ENTRY="serial_verification_gui.py"

PYINSTALLER="$(./scripts/ensure_pyinstaller.sh)"

"$PYINSTALLER" \
  --noconfirm \
  --clean \
  --windowed \
  --onefile \
  --collect-all PyQt5 \
  --name "$APP_NAME" \
  --icon "app_icon.ico" \
  --add-data "aio-2.png:." \
  --add-data "aio.png:." \
  --add-data "app_icon.ico:." \
  "$ENTRY"

echo "Built dist/$APP_NAME"
