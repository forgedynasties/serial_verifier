"""Verification service that orchestrates reboot and serial comparison."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from .adb_client import ADBClient
from .errors import SerialVerificationError
from .models import ConnectedDevice, RebootReadResult, VerificationResult, VerificationStatus

ProgressCallback = Callable[[str], None]
BARCODE_LENGTH = 14


class SerialVerificationService:
    """High-level workflow: reboot with ADB, read serial, compare with barcode."""

    def __init__(self, adb_client: ADBClient | None = None) -> None:
        self.adb_client = adb_client or ADBClient()

    def get_connected_device_serials(self) -> list[str]:
        """Return currently connected ADB device serials."""
        return self.adb_client.get_connected_device_serials()

    def get_connected_devices(self) -> list[ConnectedDevice]:
        """Return currently connected devices with USB/transport metadata."""
        return self.adb_client.get_connected_devices()

    def reboot_and_collect_serial(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> RebootReadResult:
        """Detect one connected device, reboot it, and capture post-reboot ADB serial."""
        progress = progress_callback or (lambda _: None)

        devices = self.adb_client.get_connected_devices()
        if not devices:
            raise SerialVerificationError("No connected device found in `adb devices`.")
        if len(devices) > 1:
            listed = ", ".join(d.adb_serial for d in devices)
            raise SerialVerificationError(
                f"Multiple devices detected ({listed}). Keep only one connected."
            )

        return self.reboot_and_collect_serial_for_device(
            device=devices[0],
            progress_callback=progress,
        )

    def reboot_and_collect_serial_for_device(
        self,
        device: ConnectedDevice | str,
        progress_callback: ProgressCallback | None = None,
    ) -> RebootReadResult:
        """Reboot a known device and return the ADB serial reported after reboot."""
        progress = progress_callback or (lambda _: None)

        if isinstance(device, ConnectedDevice):
            target = device
        else:
            target = ConnectedDevice(
                adb_serial=device.strip(),
                usb_path=None,
                transport_id=None,
                hardware_serial=None,
            )

        if not target.adb_serial.strip():
            raise SerialVerificationError("Device serial is empty.")

        device_serial = target.adb_serial.strip()
        progress(f"Detected ADB device before reboot: {device_serial}")
        if len(device_serial) != BARCODE_LENGTH:
            progress(
                "Initial ADB serial length is "
                f"{len(device_serial)}; reboot will continue and verification will use the "
                "ADB serial reported after reboot."
            )
        if target.usb_path:
            progress(f"Detected USB path: {target.usb_path}")
        if target.hardware_serial:
            progress(f"Detected hardware serial: {target.hardware_serial}")
        progress("Sending reboot command...")
        if target.transport_id:
            self.adb_client.reboot_device_by_transport(target.transport_id)
        else:
            self.adb_client.reboot_device(device_serial)

        progress("Waiting for device to reconnect...")
        reconnected = self.adb_client.wait_for_reconnected_device(
            expected_serial=device_serial,
            usb_path=target.usb_path,
        )
        adb_serial_after_reboot = reconnected.adb_serial.strip()
        if adb_serial_after_reboot != device_serial:
            progress(
                "ADB serial changed after reboot: "
                f"{device_serial} -> {adb_serial_after_reboot}"
            )
        progress(f"ADB serial from `adb devices` after reboot: {adb_serial_after_reboot}")

        return RebootReadResult(
            device_serial_before_reboot=device_serial,
            adb_serial_after_reboot=adb_serial_after_reboot,
            completed_at=datetime.now(),
        )

    def compare_serials(
        self,
        barcode_serial: str,
        reboot_result: RebootReadResult,
    ) -> VerificationResult:
        """Compare normalized barcode serial against reboot-captured ADB serial."""
        barcode = barcode_serial.strip()
        adb_serial = reboot_result.adb_serial_after_reboot.strip()
        device_before = reboot_result.device_serial_before_reboot.strip()

        if len(barcode) != BARCODE_LENGTH:
            return VerificationResult(
                barcode_serial=barcode,
                adb_serial=adb_serial,
                device_serial_before_reboot=device_before,
                status=VerificationStatus.ERROR,
                message=f"Invalid barcode length: expected {BARCODE_LENGTH}, got {len(barcode)}.",
                checked_at=datetime.now(),
            )

        if barcode == adb_serial:
            return VerificationResult(
                barcode_serial=barcode,
                adb_serial=adb_serial,
                device_serial_before_reboot=device_before,
                status=VerificationStatus.PASS,
                message="Barcode serial matches ADB serial.",
                checked_at=datetime.now(),
            )

        return VerificationResult(
            barcode_serial=barcode,
            adb_serial=adb_serial,
            device_serial_before_reboot=device_before,
            status=VerificationStatus.FAIL,
            message="Barcode serial does not match ADB serial.",
            checked_at=datetime.now(),
        )

    def verify_barcode(
        self,
        raw_barcode_serial: str,
        progress_callback: ProgressCallback | None = None,
    ) -> VerificationResult:
        barcode_serial = raw_barcode_serial.strip()
        if not barcode_serial:
            return VerificationResult(
                barcode_serial="",
                adb_serial="",
                device_serial_before_reboot="",
                status=VerificationStatus.ERROR,
                message="Empty barcode serial received.",
                checked_at=datetime.now(),
            )

        progress = progress_callback or (lambda _: None)
        progress(f"Barcode scan received: {barcode_serial}")

        try:
            reboot_result = self.reboot_and_collect_serial(progress_callback=progress)
            return self.compare_serials(barcode_serial=barcode_serial, reboot_result=reboot_result)
        except SerialVerificationError as exc:
            return VerificationResult(
                barcode_serial=barcode_serial,
                adb_serial="",
                device_serial_before_reboot="",
                status=VerificationStatus.ERROR,
                message=str(exc),
                checked_at=datetime.now(),
            )
        except Exception as exc:  # pylint: disable=broad-except
            return VerificationResult(
                barcode_serial=barcode_serial,
                adb_serial="",
                device_serial_before_reboot="",
                status=VerificationStatus.ERROR,
                message=f"Unexpected error: {exc}",
                checked_at=datetime.now(),
            )
