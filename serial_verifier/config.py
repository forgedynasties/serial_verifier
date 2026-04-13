"""Configuration objects for serial verification."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ADBConfig:
    """Timeout and polling configuration for ADB operations."""

    list_devices_timeout_sec: int = 10
    reboot_timeout_sec: int = 15
    wait_for_device_timeout_sec: int = 240
    get_state_timeout_sec: int = 10
    get_serial_timeout_sec: int = 10
    get_properties_timeout_sec: int = 10
    ready_poll_duration_sec: int = 90
    ready_poll_interval_sec: float = 1.0
