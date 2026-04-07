"""Unit tests for serial verification service workflow."""

from __future__ import annotations

from datetime import datetime
import unittest

from serial_verifier.errors import ADBCommandError
from serial_verifier.models import ConnectedDevice, RebootReadResult, VerificationStatus
from serial_verifier.service import SerialVerificationService


class FakeADBClient:
    def __init__(
        self,
        device_serials: list[str] | None = None,
        adb_serial_after_reboot: str | None = None,
        reboot_error: Exception | None = None,
        wait_error: Exception | None = None,
    ) -> None:
        self.device_serials = device_serials or ["ABC123"]
        self.adb_serial_after_reboot = (
            adb_serial_after_reboot
            if adb_serial_after_reboot is not None
            else self.device_serials[0]
        )
        self.reboot_error = reboot_error
        self.wait_error = wait_error
        self.last_reboot_serial: str | None = None
        self.last_wait_expected_serial: str | None = None
        self.last_wait_usb_path: str | None = None
        self.wait_for_reconnected_device_called = False

    def get_connected_device_serials(self) -> list[str]:
        return self.device_serials

    def get_connected_devices(self) -> list[ConnectedDevice]:
        return [
            ConnectedDevice(
                adb_serial=serial,
                usb_path=None,
                transport_id=None,
                hardware_serial=None,
            )
            for serial in self.device_serials
        ]

    def reboot_device(self, serial: str) -> None:
        self.last_reboot_serial = serial
        if self.reboot_error:
            raise self.reboot_error

    def wait_for_reconnected_device(
        self,
        expected_serial: str,
        usb_path: str | None = None,
    ) -> ConnectedDevice:
        self.wait_for_reconnected_device_called = True
        self.last_wait_expected_serial = expected_serial
        self.last_wait_usb_path = usb_path
        if self.wait_error:
            raise self.wait_error
        return ConnectedDevice(
            adb_serial=self.adb_serial_after_reboot,
            usb_path=usb_path,
            transport_id=None,
            hardware_serial=None,
        )


class SerialVerificationServiceTests(unittest.TestCase):
    def test_returns_pass_when_serials_match(self) -> None:
        service = SerialVerificationService(
            adb_client=FakeADBClient(device_serials=["AT070AA26XXXXX"])
        )
        result = service.verify_barcode("AT070AA26XXXXX")
        self.assertEqual(result.status, VerificationStatus.PASS)

    def test_returns_fail_when_serials_mismatch(self) -> None:
        service = SerialVerificationService(
            adb_client=FakeADBClient(device_serials=["AT070AA26AAAAA"])
        )
        result = service.verify_barcode("AT070AA26XXXXX")
        self.assertEqual(result.status, VerificationStatus.FAIL)

    def test_returns_error_when_multiple_devices_connected(self) -> None:
        service = SerialVerificationService(adb_client=FakeADBClient(device_serials=["A", "B"]))
        result = service.verify_barcode("A")
        self.assertEqual(result.status, VerificationStatus.ERROR)
        self.assertIn("Multiple devices", result.message)

    def test_returns_error_when_adb_operation_fails(self) -> None:
        service = SerialVerificationService(
            adb_client=FakeADBClient(reboot_error=ADBCommandError("reboot failed"))
        )
        result = service.verify_barcode("A")
        self.assertEqual(result.status, VerificationStatus.ERROR)
        self.assertIn("reboot failed", result.message)

    def test_reboot_and_collect_for_device(self) -> None:
        fake_adb = FakeADBClient(device_serials=["POST001"])
        service = SerialVerificationService(adb_client=fake_adb)
        result = service.reboot_and_collect_serial_for_device("PRE001")
        self.assertIsInstance(result, RebootReadResult)
        self.assertEqual(result.device_serial_before_reboot, "PRE001")
        self.assertEqual(result.adb_serial_after_reboot, "POST001")
        self.assertEqual(fake_adb.last_reboot_serial, "PRE001")
        self.assertTrue(fake_adb.wait_for_reconnected_device_called)
        self.assertEqual(fake_adb.last_wait_expected_serial, "PRE001")

    def test_verify_barcode_uses_post_reboot_serial_when_initial_serial_is_short(self) -> None:
        fake_adb = FakeADBClient(
            device_serials=["TEMP12"],
            adb_serial_after_reboot="AT070AA26XXXXX",
        )
        service = SerialVerificationService(adb_client=fake_adb)
        result = service.verify_barcode("AT070AA26XXXXX")
        self.assertEqual(result.status, VerificationStatus.PASS)
        self.assertEqual(fake_adb.last_reboot_serial, "TEMP12")
        self.assertTrue(fake_adb.wait_for_reconnected_device_called)
        self.assertEqual(fake_adb.last_wait_expected_serial, "TEMP12")

    def test_compare_serials_returns_pass(self) -> None:
        service = SerialVerificationService(adb_client=FakeADBClient())
        reboot_result = RebootReadResult(
            device_serial_before_reboot="D1",
            adb_serial_after_reboot="AT070AA26XXXXX",
            completed_at=datetime.now(),
        )
        result = service.compare_serials("AT070AA26XXXXX", reboot_result)
        self.assertEqual(result.status, VerificationStatus.PASS)

    def test_compare_serials_returns_fail(self) -> None:
        service = SerialVerificationService(adb_client=FakeADBClient())
        reboot_result = RebootReadResult(
            device_serial_before_reboot="D1",
            adb_serial_after_reboot="ADB00000000000",
            completed_at=datetime.now(),
        )
        result = service.compare_serials("AT070AA26XXXXX", reboot_result)
        self.assertEqual(result.status, VerificationStatus.FAIL)

    def test_compare_serials_invalid_length_returns_error(self) -> None:
        service = SerialVerificationService(adb_client=FakeADBClient())
        reboot_result = RebootReadResult(
            device_serial_before_reboot="D1",
            adb_serial_after_reboot="AT070AA26XXXXX",
            completed_at=datetime.now(),
        )
        result = service.compare_serials("SHORT", reboot_result)
        self.assertEqual(result.status, VerificationStatus.ERROR)


if __name__ == "__main__":
    unittest.main()
