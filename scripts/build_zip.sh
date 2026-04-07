#!/usr/bin/env bash
set -euo pipefail

APP_NAME="serialVerifier"
APP_VERSION="${APP_VERSION:-0.1.0}"
PLATFORM_TOOLS_DIR="${PLATFORM_TOOLS_DIR:-../platform-tools}"

if [ ! -x "dist/$APP_NAME" ]; then
  echo "Missing dist/$APP_NAME. Build it first with ./scripts/build_linux_app.sh"
  exit 1
fi

if [ ! -d "$PLATFORM_TOOLS_DIR" ]; then
  echo "Missing platform-tools directory at $PLATFORM_TOOLS_DIR"
  exit 1
fi

STAGE_ROOT="build/zip/$APP_NAME"
rm -rf "$STAGE_ROOT"
mkdir -p "$STAGE_ROOT"

install -m 0755 "dist/$APP_NAME" "$STAGE_ROOT/$APP_NAME"
cp -a "$PLATFORM_TOOLS_DIR" "$STAGE_ROOT/platform-tools"
install -m 0755 "packaging/zip/setup.sh" "$STAGE_ROOT/setup.sh"
install -m 0644 "packaging/zip/README.txt" "$STAGE_ROOT/README.txt"

if [ -f "aio.png" ]; then
  install -m 0644 "aio.png" "$STAGE_ROOT/aio.png"
fi
if [ -f "AIO-ICON-Serial.png" ]; then
  install -m 0644 "AIO-ICON-Serial.png" "$STAGE_ROOT/AIO-ICON-Serial.png"
fi
if [ -f "app_icon.ico" ]; then

  install -m 0644 "app_icon.ico" "$STAGE_ROOT/app_icon.ico"
fi

ZIP_NAME="${APP_NAME}_${APP_VERSION}_linux.zip"
(cd "build/zip" && python3 -m zipfile -c "../../dist/$ZIP_NAME" "$APP_NAME")
echo "Built dist/$ZIP_NAME"
