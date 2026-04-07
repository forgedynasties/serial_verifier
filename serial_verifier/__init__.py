"""Serial verification package."""


def run_app() -> None:
    """Lazy launcher to avoid importing GUI deps during backend-only usage."""
    try:
        from .gui import run_app as _run_app
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("PyQt5"):
            raise SystemExit(
                "PyQt5 is required. Install with: sudo apt-get install -y python3-pyqt5"
            ) from exc
        raise

    _run_app()


__all__ = ["run_app"]
