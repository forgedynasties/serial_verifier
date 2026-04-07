"""Background monitor for connected ADB devices."""

from __future__ import annotations

import threading
from collections.abc import Callable

from .models import ConnectedDevice
from .service import SerialVerificationService

DeviceListCallback = Callable[[list[ConnectedDevice]], None]
ErrorCallback = Callable[[str], None]


class DeviceMonitor:
    """Poll connected ADB devices in a background thread."""

    def __init__(
        self,
        service: SerialVerificationService,
        on_devices: DeviceListCallback,
        on_error: ErrorCallback,
        poll_interval_sec: float = 1.0,
    ) -> None:
        self._service = service
        self._on_devices = on_devices
        self._on_error = on_error
        self._poll_interval_sec = poll_interval_sec
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                devices = self._service.get_connected_devices()
                self._on_devices(devices)
            except Exception as exc:  # pylint: disable=broad-except
                self._on_error(str(exc))

            self._stop_event.wait(self._poll_interval_sec)
