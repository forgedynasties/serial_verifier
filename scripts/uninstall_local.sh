#!/usr/bin/env bash
set -euo pipefail

APP_NAME="serialVerifier"

rm -f "$HOME/.local/bin/$APP_NAME"
rm -f "$HOME/.local/share/applications/serialVerifier.desktop"
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/$APP_NAME.png"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
fi

echo "Uninstalled local launcher files."
