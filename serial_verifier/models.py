"""Domain models for serial verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VerificationStatus(str, Enum):
    """Verification outcome status."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


@dataclass(frozen=True)
class VerificationResult:
    """Result model for one barcode verification cycle."""

    barcode_serial: str
    adb_serial: str
    device_serial_before_reboot: str
    status: VerificationStatus
    message: str
    checked_at: datetime


@dataclass(frozen=True)
class ConnectedDevice:
    """Details for one currently connected device."""

    adb_serial: str
    usb_path: str | None
    transport_id: str | None
    hardware_serial: str | None


@dataclass(frozen=True)
class RebootReadResult:
    """Captured ADB serial details after reboot step."""

    device_serial_before_reboot: str
    adb_serial_after_reboot: str
    completed_at: datetime
