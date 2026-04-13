"""Unit tests for ADB client device metadata parsing."""

from __future__ import annotations

import unittest

from serial_verifier.adb_client import ADBClient
from serial_verifier.config import ADBConfig


class FakeADBClient(ADBClient):
    def __init__(self, responses: dict[tuple[str, ...], str]) -> None:
        super().__init__(config=ADBConfig())
        self._responses = responses

    def _run(self, args: list[str], timeout_sec: int) -> str:
        return self._responses.get(tuple(args), "")

    def _get_hardware_serial_for_usb_path(self, usb_path: str) -> str | None:
        return f"HW-{usb_path}"


class ADBClientTests(unittest.TestCase):
    def test_classify_secure_boot_enabled_from_green_state(self) -> None:
        result = ADBClient._classify_secure_boot_state("green")
        self.assertEqual(result, "green")

    def test_classify_secure_boot_disabled_from_unlocked_state(self) -> None:
        result = ADBClient._classify_secure_boot_state("orange")
        self.assertEqual(result, "orange")

    def test_classify_secure_boot_unknown_for_ambiguous_state(self) -> None:
        result = ADBClient._classify_secure_boot_state("yellow")
        self.assertEqual(result, "yellow")

    def test_get_connected_devices_includes_secure_boot_state(self) -> None:
        client = FakeADBClient(
            responses={
                ("devices", "-l"): (
                    "List of devices attached\n"
                    "ABC123 device usb:1-1 transport_id:7\n"
                ),
                ("-s", "ABC123", "shell", "getprop", "ro.boot.verifiedbootstate"): "green",
            }
        )

        devices = client.get_connected_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].adb_serial, "ABC123")
        self.assertEqual(devices[0].hardware_serial, "HW-1-1")
        self.assertEqual(devices[0].secure_boot_state, "green")


if __name__ == "__main__":
    unittest.main()
