#!/usr/bin/env python3
"""Launcher for the modular serial verification GUI."""

try:
    from serial_verifier.gui import run_app
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("PyQt5"):
        raise SystemExit(
            "PyQt5 is required. Install with: sudo apt-get install -y python3-pyqt5"
        ) from exc
    raise


if __name__ == "__main__":
    run_app()
