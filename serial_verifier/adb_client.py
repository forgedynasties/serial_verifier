"""Low-level ADB integration for serial verification."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from .config import ADBConfig
from .errors import ADBCommandError
from .models import ConnectedDevice


class ADBClient:
    """Wrapper around ADB CLI commands used by the workflow."""

    def __init__(self, config: ADBConfig | None = None) -> None:
        self.config = config or ADBConfig()
        self._hw_serial_cache: dict[str, str | None] = {}

    @staticmethod
    def _resolve_adb_path() -> str:
        env_path = os.environ.get("SERIAL_TOOL_ADB") or os.environ.get("ADB_PATH")
        if env_path:
            return env_path

        env_dir = os.environ.get("SERIAL_TOOL_ADB_DIR") or os.environ.get("ADB_DIR")
        if env_dir:
            return str(Path(env_dir) / "adb")

        exe_dir = Path(sys.executable).resolve().parent
        bundled = exe_dir / "platform-tools" / "adb"
        if bundled.exists():
            return str(bundled)

        return "adb"

    def _run(self, args: list[str], timeout_sec: int) -> str:
        adb_path = self._resolve_adb_path()
        if adb_path != "adb" and not Path(adb_path).exists():
            raise ADBCommandError(f"ADB not found at {adb_path}.")

        command = [adb_path, *args]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except FileNotFoundError as exc:
            raise ADBCommandError("`adb` is not installed or not available in PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise ADBCommandError(f"ADB command timed out: {' '.join(command)}") from exc

        if completed.returncode != 0:
            details = completed.stderr.strip() or completed.stdout.strip()
            message = details or f"ADB command failed with exit code {completed.returncode}."
            raise ADBCommandError(message)

        return completed.stdout.strip()

    def _read_sysfs_value(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return None

    def _get_hardware_serial_for_usb_path(self, usb_path: str) -> str | None:
        sysfs_path = Path("/sys/bus/usb/devices") / usb_path
        if not sysfs_path.exists():
            return None

        busnum = self._read_sysfs_value(sysfs_path / "busnum")
        devnum = self._read_sysfs_value(sysfs_path / "devnum")
        cache_key = f"{usb_path}:{busnum}:{devnum}" if busnum and devnum else usb_path

        if cache_key in self._hw_serial_cache:
            return self._hw_serial_cache[cache_key]

        product = self._read_sysfs_value(sysfs_path / "product")
        if product:
            match = re.search(r"_SN:([0-9a-fA-F]+)", product)
            if match:
                self._hw_serial_cache[cache_key] = match.group(1)
                return match.group(1)

        serial = self._read_sysfs_value(sysfs_path / "serial")
        if serial:
            self._hw_serial_cache[cache_key] = serial
            return serial

        if not busnum or not devnum:
            self._hw_serial_cache[cache_key] = None
            return None

        try:
            bus_int = int(busnum)
            dev_int = int(devnum)
        except ValueError:
            self._hw_serial_cache[cache_key] = None
            return None

        try:
            completed = subprocess.run(
                ["lsusb", "-v", "-s", f"{bus_int:03d}:{dev_int:03d}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._hw_serial_cache[cache_key] = None
            return None

        if completed.returncode != 0:
            self._hw_serial_cache[cache_key] = None
            return None

        match = re.search(r"_SN:([0-9a-fA-F]+)", completed.stdout)
        if match:
            self._hw_serial_cache[cache_key] = match.group(1)
            return match.group(1)

        match = re.search(r"iSerial\s+\d+\s+(\S+)", completed.stdout)
        if match:
            self._hw_serial_cache[cache_key] = match.group(1)
            return match.group(1)

        self._hw_serial_cache[cache_key] = None
        return None

    def get_connected_devices(self) -> list[ConnectedDevice]:
        output = self._run(["devices", "-l"], timeout_sec=self.config.list_devices_timeout_sec)
        devices: list[ConnectedDevice] = []
        for line in output.splitlines():
            clean_line = line.strip()
            if not clean_line or clean_line.startswith("List of devices attached"):
                continue

            parts = clean_line.split()
            if len(parts) < 2:
                continue

            adb_serial = parts[0]
            state = parts[1]
            if state != "device":
                continue

            usb_path = None
            transport_id = None
            for token in parts[2:]:
                if token.startswith("usb:"):
                    usb_path = token.split("usb:", 1)[1]
                elif token.startswith("transport_id:"):
                    transport_id = token.split("transport_id:", 1)[1]

            hardware_serial = (
                self._get_hardware_serial_for_usb_path(usb_path) if usb_path else None
            )
            devices.append(
                ConnectedDevice(
                    adb_serial=adb_serial,
                    usb_path=usb_path,
                    transport_id=transport_id,
                    hardware_serial=hardware_serial,
                )
            )

        return devices

    def get_connected_device_serials(self) -> list[str]:
        return [device.adb_serial for device in self.get_connected_devices()]

    def get_device_by_usb_path(self, usb_path: str) -> ConnectedDevice | None:
        for device in self.get_connected_devices():
            if device.usb_path == usb_path:
                return device
        return None

    def get_device_by_serial(self, adb_serial: str) -> ConnectedDevice | None:
        for device in self.get_connected_devices():
            if device.adb_serial == adb_serial:
                return device
        return None

    def get_reconnected_device_serial(self, expected_serial: str) -> str:
        """Return the serial shown by `adb devices` after reboot."""
        serials = self.get_connected_device_serials()
        if not serials:
            raise ADBCommandError("No connected device found in `adb devices` after reboot.")

        if expected_serial in serials:
            return expected_serial

        if len(serials) == 1:
            return serials[0]

        listed = ", ".join(serials)
        raise ADBCommandError(
            "Could not determine rebooted device serial from `adb devices`. "
            f"Expected `{expected_serial}`. Found: {listed}."
        )

    def wait_for_reconnected_device(
        self,
        expected_serial: str,
        usb_path: str | None = None,
    ) -> ConnectedDevice:
        """Wait for the rebooted device to return, even if its ADB serial changes."""
        deadline = time.monotonic() + self.config.ready_poll_duration_sec
        while time.monotonic() < deadline:
            devices = self.get_connected_devices()

            if usb_path:
                for device in devices:
                    if device.usb_path == usb_path:
                        return device

            for device in devices:
                if device.adb_serial == expected_serial:
                    return device

            if len(devices) == 1:
                return devices[0]

            time.sleep(self.config.ready_poll_interval_sec)

        if usb_path:
            raise ADBCommandError(
                "Device did not reconnect after reboot on the original USB path."
            )

        raise ADBCommandError("Device did not reconnect after reboot with a usable ADB serial.")

    def reboot_device(self, serial: str) -> None:
        self._run(["-s", serial, "reboot"], timeout_sec=self.config.reboot_timeout_sec)

    def reboot_device_by_transport(self, transport_id: str) -> None:
        self._run(["-t", transport_id, "reboot"], timeout_sec=self.config.reboot_timeout_sec)

    def wait_until_ready(self, serial: str) -> None:
        self._run(["-s", serial, "wait-for-device"], timeout_sec=self.config.wait_for_device_timeout_sec)

        deadline = time.monotonic() + self.config.ready_poll_duration_sec
        while time.monotonic() < deadline:
            try:
                state = self._run(
                    ["-s", serial, "get-state"],
                    timeout_sec=self.config.get_state_timeout_sec,
                )
            except ADBCommandError:
                state = ""

            if state == "device":
                return

            time.sleep(self.config.ready_poll_interval_sec)

        raise ADBCommandError("Device did not become ready after reboot.")

    def wait_until_ready_by_usb_path(self, usb_path: str) -> ConnectedDevice:
        deadline = time.monotonic() + self.config.ready_poll_duration_sec
        while time.monotonic() < deadline:
            device = self.get_device_by_usb_path(usb_path)
            if device:
                return device
            time.sleep(self.config.ready_poll_interval_sec)

        raise ADBCommandError("Device did not become ready after reboot.")

    def get_device_serial(self, serial: str) -> str:
        adb_serial = self._run(
            ["-s", serial, "get-serialno"],
            timeout_sec=self.config.get_serial_timeout_sec,
        ).strip()
        if not adb_serial or adb_serial == "unknown":
            raise ADBCommandError("Could not read device serial number from ADB.")
        return adb_serial
