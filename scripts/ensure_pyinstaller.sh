#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="${VENV_DIR:-.venv}"

if [ -x "$VENV_DIR/bin/pyinstaller" ]; then
  if "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1; then
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("PyQt5") else 1)
PY
    echo "$VENV_DIR/bin/pyinstaller"
    exit 0
  fi
  "$VENV_DIR/bin/pip" install PyQt5 >&2 || true
  if "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1; then
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("PyQt5") else 1)
PY
    echo "$VENV_DIR/bin/pyinstaller"
    exit 0
  fi
  echo "PyQt5 is missing in $VENV_DIR. Delete it and rerun (rm -rf $VENV_DIR)." >&2
  exit 1
fi

if command -v pyinstaller >/dev/null 2>&1; then
  command -v pyinstaller
  exit 0
fi

VENV_ARGS=()
if python3 - <<'PY' >/dev/null 2>&1; then
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("PyQt5") else 1)
PY
  VENV_ARGS+=(--system-site-packages)
fi

if ! python3 -m venv "${VENV_ARGS[@]}" "$VENV_DIR" >/dev/null 2>&1; then
  echo "Failed to create venv. Install python3-venv and try again." >&2
  exit 1
fi

"$VENV_DIR/bin/pip" install --upgrade pip >/dev/null 2>&1 || true
"$VENV_DIR/bin/pip" install pyinstaller Pillow >&2

if ! "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1; then
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("PyQt5") else 1)
PY
  "$VENV_DIR/bin/pip" install PyQt5 >&2
fi

if ! "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1; then
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("PyQt5") else 1)
PY
  echo "PyQt5 is missing in the build environment. Install python3-pyqt5 or pip install PyQt5 in the venv." >&2
  exit 1
fi

if [ ! -x "$VENV_DIR/bin/pyinstaller" ]; then
  echo "pyinstaller install failed in venv." >&2
  exit 1
fi

echo "$VENV_DIR/bin/pyinstaller"
