"""PyQt GUI for serial verification with reboot + live barcode capture."""

from __future__ import annotations

import threading
from datetime import datetime

from PyQt5.QtCore import QObject, QSignalBlocker, Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .device_monitor import DeviceMonitor
from .embedded_assets import AIO_2_PNG_B64, AIO_PNG_B64, load_app_icon, load_pixmap
from .models import ConnectedDevice, RebootReadResult, VerificationResult, VerificationStatus
from .service import SerialVerificationService

COLOR_BG = "#eef4f7"
COLOR_CARD = "#ffffff"
COLOR_BORDER = "#d6dfe7"
COLOR_TEXT = "#173042"
COLOR_MUTED = "#667889"
COLOR_PRIMARY = "#16324f"
COLOR_ACCENT = "#0d7c86"
COLOR_TABLE_HEADER = "#eaf0f5"
COLOR_TABLE_ALT = "#f7fafc"
COLOR_INPUT_BG = "#ffffff"
COLOR_INPUT_BORDER = "#bccad6"
COLOR_BTN_BG = "#0d7c86"
COLOR_BTN_HOVER = "#0b6972"
COLOR_BTN_DISABLED = "#9fb1bc"

COLOR_INFO = "#0d6f89"
COLOR_PASS = "#1c7c54"
COLOR_FAIL = "#c62828"
COLOR_ERROR = "#8f1d1d"
COLOR_NEUTRAL = "#475569"
COLOR_WARN = "#b26a00"
COLOR_WARN_BG = "#fff4db"
COLOR_FAIL_BG = "#fde7e7"
COLOR_PASS_BG = "#e7f6ee"
BARCODE_LENGTH = 14
LOGO_HEIGHT = 46


class _UIBridge(QObject):
    """Bridge signals to ensure worker callbacks update GUI on main thread."""

    progress = pyqtSignal(str)
    monitor_devices = pyqtSignal(object)
    monitor_error = pyqtSignal(str)
    reboot_done = pyqtSignal(object)


class SerialVerificationMainWindow(QMainWindow):
    """Desktop UI: auto-start reboot + barcode verification per detected device."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Serial Verification Tool")
        self.resize(1040, 700)
        self.setMinimumSize(920, 620)

        self.total_count = 0
        self.pass_count = 0
        self.fail_count = 0
        self.error_count = 0

        self._cycle_active = False
        self._cycle_barcode: str | None = None
        self._cycle_reboot_result: RebootReadResult | None = None
        self._cycle_started_at: datetime | None = None
        self._pending_barcode: str | None = None
        self._latest_devices: list[ConnectedDevice] = []
        self._last_auto_started_key: str | None = None
        self._cycle_device: ConnectedDevice | None = None
        self._is_closing = False
        self._content_widget: QWidget | None = None
        self._outer_layout: QVBoxLayout | None = None

        self.service = SerialVerificationService()
        self.bridge = _UIBridge()
        self.bridge.progress.connect(self._append_log)
        self.bridge.monitor_devices.connect(self._on_devices_updated)
        self.bridge.monitor_error.connect(self._on_monitor_error)
        self.bridge.reboot_done.connect(self._on_reboot_done)

        self.device_monitor = DeviceMonitor(
            service=self.service,
            on_devices=lambda serials: self.bridge.monitor_devices.emit(serials),
            on_error=lambda message: self.bridge.monitor_error.emit(message),
            poll_interval_sec=1.0,
        )

        self._build_ui()
        self._apply_app_icon()
        self._apply_theme()
        self._refresh_minimums()
        self.device_monitor.start()
        self._append_log("Application started. Waiting for connected device.")
        self._focus_barcode_entry()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll = QScrollArea(central)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        root_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        outer_layout = QVBoxLayout(content)
        outer_layout.setContentsMargins(18, 18, 18, 18)
        outer_layout.setSpacing(12)
        self._content_widget = content
        self._outer_layout = outer_layout

        header = QWidget(central)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(12)

        left_logo = self._make_logo_label(AIO_PNG_B64, "logoLeft")
        right_logo = self._make_logo_label(AIO_2_PNG_B64, "logoRight")

        title_block = QWidget(header)
        title_layout = QVBoxLayout(title_block)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(4)

        title = QLabel("Serial Verification")
        title.setObjectName("title")
        title_layout.addWidget(title)

        instructions = QLabel(
            "Shows live ADB and hardware serials, reboots the detected device automatically, "
            "and verifies the 14-character barcode against the ADB serial reported after reboot."
        )
        instructions.setObjectName("subtitle")
        instructions.setWordWrap(True)
        title_layout.addWidget(instructions)

        header_layout.addWidget(left_logo)
        header_layout.addWidget(title_block, stretch=1)
        header_layout.addWidget(right_logo)
        outer_layout.addWidget(header)

        status_card = QFrame(central)
        status_card.setObjectName("card")
        status_layout = QGridLayout(status_card)
        status_layout.setContentsMargins(16, 16, 16, 16)
        status_layout.setHorizontalSpacing(12)
        status_layout.setVerticalSpacing(10)

        label_style = f"color: {COLOR_MUTED}; font-weight: 600;"

        def add_field_label(text: str, row: int) -> None:
            label = QLabel(text)
            label.setStyleSheet(label_style)
            status_layout.addWidget(label, row, 0)

        add_field_label("Status:", 0)
        self.status_label = QLabel("Waiting for connected device...")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(44)
        status_layout.addWidget(self.status_label, 0, 1, 1, 3)
        self._set_status("Waiting for connected device...", COLOR_INFO)

        add_field_label("Connected ADB:", 1)
        self.connected_adb_label = QLabel("-")
        self.connected_adb_label.setStyleSheet("font-family: monospace;")
        self.connected_adb_label.setWordWrap(True)
        status_layout.addWidget(self.connected_adb_label, 1, 1, 1, 3)

        add_field_label("Connected HW:", 2)
        self.connected_hw_label = QLabel("-")
        self.connected_hw_label.setStyleSheet("font-family: monospace;")
        self.connected_hw_label.setWordWrap(True)
        status_layout.addWidget(self.connected_hw_label, 2, 1, 1, 3)

        add_field_label("Secure Boot:", 3)
        self.connected_secure_boot_label = QLabel("-")
        self.connected_secure_boot_label.setStyleSheet("font-family: monospace;")
        self.connected_secure_boot_label.setWordWrap(True)
        status_layout.addWidget(self.connected_secure_boot_label, 3, 1, 1, 3)

        add_field_label("USB Path:", 4)
        self.connected_usb_label = QLabel("-")
        self.connected_usb_label.setStyleSheet("font-family: monospace;")
        self.connected_usb_label.setWordWrap(True)
        status_layout.addWidget(self.connected_usb_label, 4, 1, 1, 3)

        add_field_label("Barcode Input:", 5)
        self.barcode_entry = QLineEdit()
        self.barcode_entry.setPlaceholderText("Scan barcode (14 chars)")
        self.barcode_entry.textChanged.connect(self._on_barcode_changed)
        self.barcode_entry.returnPressed.connect(self._on_barcode_submitted)
        self.barcode_entry.setMinimumHeight(38)
        self.barcode_entry.setClearButtonEnabled(True)
        status_layout.addWidget(self.barcode_entry, 5, 1)

        self.verify_button = QPushButton("Submit Barcode")
        self.verify_button.setEnabled(False)
        self.verify_button.clicked.connect(self._on_barcode_submitted)
        self.verify_button.setMinimumHeight(38)
        status_layout.addWidget(self.verify_button, 5, 2)

        barcode_hint = QLabel("Auto-captures at 14 chars. Press Enter to submit.")
        barcode_hint.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        status_layout.addWidget(barcode_hint, 6, 1, 1, 3)

        add_field_label("Stored Barcode:", 7)
        self.stored_barcode_label = QLabel("-")
        self.stored_barcode_label.setStyleSheet("font-family: monospace;")
        status_layout.addWidget(self.stored_barcode_label, 7, 1, 1, 3)

        add_field_label("Last Barcode:", 8)
        self.last_barcode_label = QLabel("-")
        self.last_barcode_label.setStyleSheet("font-family: monospace;")
        status_layout.addWidget(self.last_barcode_label, 8, 1, 1, 3)

        add_field_label("ADB Before Reboot:", 9)
        self.last_adb_before_label = QLabel("-")
        self.last_adb_before_label.setStyleSheet("font-family: monospace;")
        status_layout.addWidget(self.last_adb_before_label, 9, 1, 1, 3)

        add_field_label("ADB After Reboot:", 10)
        self.last_adb_after_label = QLabel("-")
        self.last_adb_after_label.setStyleSheet("font-family: monospace;")
        status_layout.addWidget(self.last_adb_after_label, 10, 1, 1, 3)

        add_field_label("Last Result:", 11)
        self.last_result_label = QLabel("No checks yet")
        self.last_result_label.setStyleSheet(f"font-weight: 700; color: {COLOR_NEUTRAL};")
        self.last_result_label.setWordWrap(True)
        status_layout.addWidget(self.last_result_label, 11, 1, 1, 3)

        add_field_label("Last Duration:", 12)
        self.last_duration_label = QLabel("-")
        self.last_duration_label.setStyleSheet("font-family: monospace;")
        status_layout.addWidget(self.last_duration_label, 12, 1, 1, 3)

        self.stats_label = QLabel("Total: 0 | Pass: 0 | Fail: 0 | Errors: 0")
        self.stats_label.setStyleSheet(
            f"font-weight: 700; color: {COLOR_PRIMARY}; background-color: {COLOR_TABLE_HEADER}; "
            f"border-radius: 8px; padding: 8px 12px;"
        )
        status_layout.addWidget(self.stats_label, 13, 0, 1, 4)

        status_layout.setColumnStretch(1, 1)
        outer_layout.addWidget(status_card)

        results_card = QFrame(central)
        results_card.setObjectName("card")
        results_layout = QVBoxLayout(results_card)
        results_layout.setContentsMargins(12, 12, 12, 12)
        results_layout.setSpacing(8)

        results_header = QLabel("Recent Results")
        results_header.setStyleSheet("font-weight: 700;")
        results_layout.addWidget(results_header)

        self.history_table = QTableWidget(0, 7)
        self.history_table.setHorizontalHeaderLabels(
            [
                "Time",
                "Status",
                "Barcode Serial",
                "ADB Before",
                "ADB After",
                "Duration",
                "Details",
            ]
        )
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setMinimumHeight(240)
        self.history_table.setColumnWidth(0, 90)
        self.history_table.setColumnWidth(1, 80)
        self.history_table.setColumnWidth(2, 160)
        self.history_table.setColumnWidth(3, 160)
        self.history_table.setColumnWidth(4, 160)
        self.history_table.setColumnWidth(5, 90)
        results_layout.addWidget(self.history_table, stretch=1)
        outer_layout.addWidget(results_card, stretch=2)

        logs_card = QFrame(central)
        logs_card.setObjectName("card")
        logs_layout = QVBoxLayout(logs_card)
        logs_layout.setContentsMargins(12, 12, 12, 12)
        logs_layout.setSpacing(8)

        logs_header_layout = QHBoxLayout()
        logs_header = QLabel("Logs")
        logs_header.setStyleSheet("font-weight: 700;")
        logs_header_layout.addWidget(logs_header)
        logs_header_layout.addStretch(1)

        clear_button = QPushButton("Clear Logs")
        clear_button.setObjectName("secondary")
        clear_button.clicked.connect(self._clear_logs)
        logs_header_layout.addWidget(clear_button)
        logs_layout.addLayout(logs_header_layout)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(160)
        logs_layout.addWidget(self.log_box, stretch=1)
        outer_layout.addWidget(logs_card, stretch=1)

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background-color: {COLOR_BG};
            }}
            * {{
                font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif;
                color: {COLOR_TEXT};
            }}
            QLabel#title {{
                font-size: 22px;
                font-weight: 700;
                color: {COLOR_PRIMARY};
            }}
            QLabel#subtitle {{
                font-size: 12px;
                color: {COLOR_MUTED};
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: transparent;
            }}
            QFrame#card {{
                background-color: {COLOR_CARD};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
            QLineEdit {{
                background-color: {COLOR_INPUT_BG};
                border: 1px solid {COLOR_INPUT_BORDER};
                border-radius: 10px;
                padding: 7px 10px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLOR_ACCENT};
            }}
            QPushButton {{
                background-color: {COLOR_BTN_BG};
                color: #ffffff;
                border: none;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BTN_HOVER};
            }}
            QPushButton:disabled {{
                background-color: {COLOR_BTN_DISABLED};
                color: #ffffff;
            }}
            QPushButton#secondary {{
                background-color: #e5e7eb;
                color: {COLOR_TEXT};
            }}
            QPushButton#secondary:hover {{
                background-color: #d9dde3;
            }}
            QTableWidget {{
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
                gridline-color: {COLOR_BORDER};
                background-color: {COLOR_CARD};
            }}
            QHeaderView::section {{
                background-color: {COLOR_TABLE_HEADER};
                color: {COLOR_TEXT};
                font-weight: 600;
                border: none;
                padding: 8px 6px;
            }}
            QPlainTextEdit {{
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
                background-color: {COLOR_TABLE_ALT};
            }}
            """
        )

    def _apply_app_icon(self) -> None:
        icon = load_app_icon()
        if icon.isNull():
            return
        self.setWindowIcon(icon)
        app = QApplication.instance()
        if app:
            app.setWindowIcon(icon)

    def _make_logo_label(self, b64: str, name: str) -> QLabel:
        label = QLabel()
        label.setObjectName(name)
        label.setAlignment(Qt.AlignCenter)
        label.setFixedHeight(LOGO_HEIGHT)
        pixmap = load_pixmap(b64)
        if pixmap.isNull():
            label.hide()
            return label
        scaled = pixmap.scaledToHeight(LOGO_HEIGHT, Qt.SmoothTransformation)
        label.setPixmap(scaled)
        return label

    def _refresh_minimums(self) -> None:
        if not self._content_widget or not self._outer_layout:
            return
        self._content_widget.setMinimumSize(self._outer_layout.sizeHint())

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            "font-weight: 700; "
            f"color: {color}; "
            f"background-color: {self._status_background(color)}; "
            f"border: 1px solid {self._status_border(color)}; "
            "border-radius: 10px; padding: 10px 12px;"
        )

    def _set_verify_enabled_by_devices(self) -> None:
        self.verify_button.setEnabled(bool(self.barcode_entry.text().strip()))

    def _cancel_active_cycle(self, reason: str, color: str, clear_pending: bool = True) -> None:
        if not self._cycle_active:
            return
        self._cycle_active = False
        self._cycle_barcode = None
        self._cycle_reboot_result = None
        self._cycle_started_at = None
        self._cycle_device = None
        self._last_auto_started_key = None
        if clear_pending:
            self._pending_barcode = None
            self.stored_barcode_label.setText("-")
            self._clear_barcode_input()
        self.barcode_entry.setReadOnly(False)
        self._set_verify_enabled_by_devices()
        self._focus_barcode_entry()
        self._append_log(reason)
        self._set_status(reason, color)

    @staticmethod
    def _normalize_barcode(text: str) -> str:
        return "".join(ch for ch in text.upper() if ch.isalnum())

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 0:
            seconds = 0.0
        if seconds < 60:
            return f"{seconds:.1f}s"
        rounded = int(round(seconds))
        minutes, sec = divmod(rounded, 60)
        if minutes < 60:
            return f"{minutes:02d}:{sec:02d}"
        hours, minutes = divmod(minutes, 60)
        return f"{hours:d}:{minutes:02d}:{sec:02d}"

    @staticmethod
    def _device_key(device: ConnectedDevice) -> str:
        return device.usb_path or device.adb_serial

    @staticmethod
    def _format_device_label(device: ConnectedDevice) -> str:
        parts = [f"ADB:{device.adb_serial or 'unknown'}"]
        parts.append(f"HW:{device.hardware_serial or 'unknown'}")
        parts.append(
            f"SB:{SerialVerificationMainWindow._format_secure_boot_summary(device.secure_boot_state)}"
        )
        if device.usb_path:
            parts.append(f"USB:{device.usb_path}")
        return " | ".join(parts)

    @staticmethod
    def _format_secure_boot_summary(state: str | None) -> str:
        normalized_state = (state or "").strip().lower()
        if normalized_state in {"", "-", "unknown", "none", "n/a"}:
            return "-"
        if normalized_state == "green":
            return "enabled"
        if normalized_state in {"orange", "yellow", "red"}:
            return f"disabled ({normalized_state})"
        return f"disabled ({normalized_state})"

    @staticmethod
    def _secure_boot_badge_colors(state: str | None) -> tuple[str, str, str]:
        normalized_state = (state or "").strip().lower()
        if normalized_state in {"", "-", "unknown", "none", "n/a"}:
            return (COLOR_NEUTRAL, COLOR_TABLE_ALT, COLOR_INPUT_BORDER)
        if normalized_state == "green":
            return (COLOR_PASS, COLOR_PASS_BG, COLOR_PASS)
        if normalized_state == "orange":
            return (COLOR_WARN, COLOR_WARN_BG, COLOR_WARN)
        if normalized_state == "yellow":
            return ("#8a6a00", "#fff8cc", "#c9a227")
        if normalized_state == "red":
            return (COLOR_FAIL, COLOR_FAIL_BG, COLOR_FAIL)
        return (COLOR_NEUTRAL, COLOR_TABLE_ALT, COLOR_INPUT_BORDER)

    def _set_secure_boot_label(self, state: str | None, multiple: bool = False) -> None:
        if multiple:
            self.connected_secure_boot_label.setText(state or "-")
            self.connected_secure_boot_label.setStyleSheet("font-family: monospace;")
            return

        text = self._format_secure_boot_summary(state)
        fg_color, bg_color, border_color = self._secure_boot_badge_colors(state)
        self.connected_secure_boot_label.setText(text)
        self.connected_secure_boot_label.setStyleSheet(
            "font-family: monospace; "
            "font-weight: 700; "
            f"color: {fg_color}; "
            f"background-color: {bg_color}; "
            f"border: 1px solid {border_color}; "
            "border-radius: 9px; "
            "padding: 6px 10px;"
        )

    def _set_connected_device_labels(
        self,
        adb_value: str = "-",
        hw_value: str = "-",
        secure_boot_value: str = "-",
        usb_value: str = "-",
        multiple: bool = False,
    ) -> None:
        self.connected_adb_label.setText(adb_value)
        self.connected_hw_label.setText(hw_value)
        self._set_secure_boot_label(secure_boot_value, multiple=multiple)
        self.connected_usb_label.setText(usb_value)

    def _show_connected_device(self, device: ConnectedDevice | None) -> None:
        if device is None:
            self._set_connected_device_labels()
            return

        self._set_connected_device_labels(
            adb_value=device.adb_serial or "-",
            hw_value=device.hardware_serial or "-",
            secure_boot_value=device.secure_boot_state or "-",
            usb_value=device.usb_path or "-",
        )

    def _store_pending_barcode(self, normalized: str, source: str) -> None:
        captured = normalized[:BARCODE_LENGTH]
        if len(normalized) > BARCODE_LENGTH:
            with QSignalBlocker(self.barcode_entry):
                self.barcode_entry.setText(captured)
            self._append_log(
                "Barcode input included extra characters; using first "
                f"{BARCODE_LENGTH}: {captured}"
            )

        if len(captured) < BARCODE_LENGTH:
            self._append_log(
                f"Barcode capture skipped: need {BARCODE_LENGTH} chars, got {len(captured)}."
            )
            return

        if captured == self._pending_barcode:
            return

        self._pending_barcode = captured
        self.stored_barcode_label.setText(captured)
        self._set_verify_enabled_by_devices()

        if source == "manual":
            self._append_log(f"Barcode stored: {captured}")
        else:
            self._append_log(f"Barcode captured and stored: {captured}")

        if not self._cycle_active:
            self._set_status("Barcode stored. Waiting for device...", COLOR_INFO)
        elif self._cycle_reboot_result:
            self._set_status("Barcode stored. Finalizing verification...", COLOR_INFO)
        else:
            self._set_status("Barcode stored. Waiting for device to be ready...", COLOR_INFO)

        self._attempt_finalize_cycle()

    def _on_devices_updated(self, serials: object) -> None:
        if self._is_closing:
            return

        self._latest_devices = list(serials) if isinstance(serials, list) else []
        if len(self._latest_devices) == 1:
            detected_device = self._latest_devices[0]
            device_key = self._device_key(detected_device)
            self._show_connected_device(detected_device)
            if not self._cycle_active and device_key != self._last_auto_started_key:
                self._append_log(
                    "Device detected. Starting automatic cycle: "
                    f"{self._format_device_label(detected_device)}"
                )
                self._set_status("Device detected. Starting automatic verification...", COLOR_INFO)
                self._start_verification_cycle(detected_device)
        elif len(self._latest_devices) == 0:
            self._show_connected_device(None)
            if self._cycle_active:
                if self._cycle_reboot_result is None:
                    if self._pending_barcode:
                        self._set_status(
                            "Device rebooting; barcode stored. Waiting to reconnect...",
                            COLOR_INFO,
                        )
                    else:
                        self._set_status(
                            "Device rebooting; waiting to reconnect...", COLOR_INFO
                        )
                else:
                    self._cancel_active_cycle(
                        "Device disconnected. Waiting for next device...", COLOR_INFO
                    )
            else:
                self._last_auto_started_key = None
                self._set_status("Waiting for connected device...", COLOR_INFO)
        else:
            adb_labels = ", ".join(device.adb_serial or "-" for device in self._latest_devices)
            hw_labels = ", ".join(device.hardware_serial or "-" for device in self._latest_devices)
            secure_boot_labels = ", ".join(
                self._format_secure_boot_summary(device.secure_boot_state)
                for device in self._latest_devices
            )
            usb_labels = ", ".join(device.usb_path or "-" for device in self._latest_devices)
            self._set_connected_device_labels(
                adb_labels,
                hw_labels,
                secure_boot_labels,
                usb_labels,
                multiple=True,
            )
            if self._cycle_active:
                self._cancel_active_cycle(
                    "Multiple devices detected. Keep one connected.", COLOR_FAIL
                )
            else:
                self._last_auto_started_key = None
                self._set_status("Multiple devices detected. Keep one connected.", COLOR_FAIL)

        self._set_verify_enabled_by_devices()

    def _on_monitor_error(self, message: str) -> None:
        if self._is_closing:
            return
        self._append_log(f"Device monitor error: {message}")
        if not self._cycle_active:
            self._set_status("ADB monitor error. Check ADB connection.", COLOR_ERROR)

    def _start_verification_cycle(self, device: ConnectedDevice | None = None) -> None:
        if self._cycle_active:
            return

        resolved_device = device
        if resolved_device is None:
            if len(self._latest_devices) != 1:
                self._set_status("Cannot start: one device is required.", COLOR_FAIL)
                self._set_verify_enabled_by_devices()
                return
            resolved_device = self._latest_devices[0]

        self._cycle_active = True
        self._cycle_barcode = None
        self._cycle_reboot_result = None
        self._cycle_started_at = datetime.now()
        self._cycle_device = resolved_device
        self._last_auto_started_key = self._device_key(resolved_device)
        self._set_verify_enabled_by_devices()

        self.last_barcode_label.setText("-")
        self.last_adb_before_label.setText(resolved_device.adb_serial or "-")
        self.last_adb_after_label.setText("-")
        if self._pending_barcode:
            with QSignalBlocker(self.barcode_entry):
                self.barcode_entry.setText(self._pending_barcode)
        else:
            self._clear_barcode_input()
        self.barcode_entry.setReadOnly(False)
        self._set_verify_enabled_by_devices()
        self._focus_barcode_entry()

        self._set_status("Verification started. Rebooting device, waiting barcode...", COLOR_INFO)
        self._append_log(
            "Verification cycle started for device: "
            f"{self._format_device_label(resolved_device)}"
        )

        reboot_thread = threading.Thread(
            target=self._reboot_worker,
            args=(resolved_device,),
            daemon=True,
        )
        reboot_thread.start()

    def _reboot_worker(self, device: ConnectedDevice) -> None:
        try:
            result = self.service.reboot_and_collect_serial_for_device(
                device=device,
                progress_callback=lambda message: self.bridge.progress.emit(message),
            )
            self.bridge.reboot_done.emit(result)
        except Exception as exc:  # pylint: disable=broad-except
            self.bridge.reboot_done.emit(exc)

    def _on_reboot_done(self, payload: object) -> None:
        if self._is_closing or not self._cycle_active:
            return

        if isinstance(payload, Exception):
            result = VerificationResult(
                barcode_serial=self._cycle_barcode or self._pending_barcode or "",
                adb_serial="",
                device_serial_before_reboot="",
                status=VerificationStatus.ERROR,
                message=str(payload),
                checked_at=datetime.now(),
            )
            self._record_result(result)
            self._finish_cycle()
            return

        if not isinstance(payload, RebootReadResult):
            result = VerificationResult(
                barcode_serial=self._cycle_barcode or self._pending_barcode or "",
                adb_serial="",
                device_serial_before_reboot="",
                status=VerificationStatus.ERROR,
                message="Unexpected reboot worker payload.",
                checked_at=datetime.now(),
            )
            self._record_result(result)
            self._finish_cycle()
            return

        self._cycle_reboot_result = payload
        self.last_adb_before_label.setText(payload.device_serial_before_reboot or "-")
        self.last_adb_after_label.setText(payload.adb_serial_after_reboot or "-")
        self._append_log(
            "Reboot completed; waiting barcode."
            if not (self._cycle_barcode or self._pending_barcode)
            else "Reboot completed; barcode already stored."
        )
        self._attempt_finalize_cycle()

    def _on_barcode_changed(self, text: str) -> None:
        normalized = self._normalize_barcode(text)
        if normalized != text:
            with QSignalBlocker(self.barcode_entry):
                self.barcode_entry.setText(normalized)

        self._set_verify_enabled_by_devices()

        if not normalized:
            if self._pending_barcode:
                self._pending_barcode = None
                self.stored_barcode_label.setText("-")
                self._append_log("Stored barcode cleared.")
                self._attempt_finalize_cycle()
            return

        if len(normalized) < BARCODE_LENGTH:
            return

        self._store_pending_barcode(normalized, source="auto")

    def _on_barcode_submitted(self) -> None:
        raw_text = self.barcode_entry.text()
        normalized = self._normalize_barcode(raw_text)
        if normalized != raw_text:
            with QSignalBlocker(self.barcode_entry):
                self.barcode_entry.setText(normalized)

        if not normalized:
            self._append_log("Barcode submit ignored: empty input.")
            return

        if len(normalized) < BARCODE_LENGTH:
            self._append_log(
                f"Barcode too short ({len(normalized)}/{BARCODE_LENGTH}). Continue scanning."
            )
            if self._cycle_active:
                color = COLOR_FAIL if self._cycle_reboot_result else COLOR_INFO
                self._set_status(
                    f"Barcode too short ({len(normalized)}/{BARCODE_LENGTH}). Continue scanning...",
                    color,
                )
            return

        self._store_pending_barcode(normalized, source="manual")

    def _attempt_finalize_cycle(self) -> None:
        if not self._cycle_active:
            return

        barcode_value = self._cycle_barcode or self._pending_barcode

        if barcode_value and self._cycle_reboot_result:
            if self._cycle_barcode is None:
                self._cycle_barcode = barcode_value
            result = self.service.compare_serials(
                barcode_serial=self._cycle_barcode,
                reboot_result=self._cycle_reboot_result,
            )
            self._record_result(result)
            if result.status == VerificationStatus.PASS:
                self._finish_cycle()
            else:
                self._prepare_barcode_retry(result.status)
            return

        if self._cycle_reboot_result and not barcode_value:
            self._set_status(
                f"Device ready. Waiting barcode ({BARCODE_LENGTH} chars)...",
                COLOR_INFO,
            )
            return

        if barcode_value and not self._cycle_reboot_result:
            self._set_status("Barcode stored. Waiting reboot to finish...", COLOR_INFO)
            return

        self._set_status("Rebooting and waiting barcode...", COLOR_INFO)

    def _prepare_barcode_retry(self, status: VerificationStatus) -> None:
        """Keep same rebooted device active and allow barcode rescan."""
        self._cycle_barcode = None
        self._pending_barcode = None
        self.stored_barcode_label.setText("-")
        self._clear_barcode_input()
        self.barcode_entry.setReadOnly(False)
        self._set_verify_enabled_by_devices()
        self._focus_barcode_entry()

        if status == VerificationStatus.FAIL:
            self._append_log("Mismatch detected. Scan barcode again for the same device.")
            self._set_status(
                f"Mismatch. Rescan barcode ({BARCODE_LENGTH} chars) for same device.",
                COLOR_FAIL,
            )
            return

        self._append_log("Verification error. Scan barcode again for the same device.")
        self._set_status(
            f"Rescan barcode ({BARCODE_LENGTH} chars) for same device.",
            COLOR_ERROR,
        )

    def _record_result(self, result: VerificationResult) -> None:
        self.total_count += 1
        self.last_barcode_label.setText(result.barcode_serial or "-")
        self.last_adb_before_label.setText(result.device_serial_before_reboot or "-")
        self.last_adb_after_label.setText(result.adb_serial or "-")
        self.last_result_label.setText(f"{result.status.value}: {result.message}")

        duration_text = "-"
        if self._cycle_started_at:
            elapsed = (result.checked_at - self._cycle_started_at).total_seconds()
            duration_text = self._format_duration(elapsed)
        self.last_duration_label.setText(duration_text)

        if result.status == VerificationStatus.PASS:
            self.pass_count += 1
            color = COLOR_PASS
            status_line = "PASS."
        elif result.status == VerificationStatus.FAIL:
            self.fail_count += 1
            color = COLOR_FAIL
            status_line = "FAIL."
        else:
            self.error_count += 1
            color = COLOR_ERROR
            status_line = "ERROR."

        self.last_result_label.setStyleSheet(f"font-weight: 700; color: {color};")
        if duration_text != "-":
            self._set_status(
                f"{status_line} Duration {duration_text}. Ready for next verification.",
                color,
            )
        else:
            self._set_status(f"{status_line} Ready for next verification.", color)
        self.stats_label.setText(
            f"Total: {self.total_count} | "
            f"Pass: {self.pass_count} | "
            f"Fail: {self.fail_count} | "
            f"Errors: {self.error_count}"
        )

        self._append_result_row(result, duration_text)
        self._append_log(f"Result [{result.status.value}] {result.message}")
        if duration_text != "-":
            self._append_log(f"Cycle duration: {duration_text}")

    def _finish_cycle(self) -> None:
        self._cycle_active = False
        self._cycle_barcode = None
        self._cycle_reboot_result = None
        self._cycle_started_at = None
        self._cycle_device = None
        self._pending_barcode = None
        self.stored_barcode_label.setText("-")
        self._clear_barcode_input()
        self.barcode_entry.setReadOnly(False)
        self._set_verify_enabled_by_devices()
        self._focus_barcode_entry()

    def _append_result_row(self, result: VerificationResult, duration_text: str) -> None:
        self.history_table.insertRow(0)
        timestamp = result.checked_at.strftime("%H:%M:%S")
        values = [
            timestamp,
            result.status.value,
            result.barcode_serial or "-",
            result.device_serial_before_reboot or "-",
            result.adb_serial or "-",
            duration_text,
            result.message,
        ]

        row_background = QColor(self._status_background(self._status_color(result.status)))
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setBackground(row_background)
            if col == 1:
                item.setForeground(QColor(self._status_color(result.status)))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.history_table.setItem(0, col, item)

        while self.history_table.rowCount() > 200:
            self.history_table.removeRow(self.history_table.rowCount() - 1)

    @staticmethod
    def _status_color(status: VerificationStatus) -> str:
        if status == VerificationStatus.PASS:
            return COLOR_PASS
        if status == VerificationStatus.FAIL:
            return COLOR_FAIL
        return COLOR_ERROR

    @staticmethod
    def _status_background(color: str) -> str:
        if color == COLOR_PASS:
            return "#e8f5ee"
        if color == COLOR_FAIL:
            return "#fdecec"
        if color == COLOR_ERROR:
            return "#f9e9e9"
        return "#e1f0f5"

    @staticmethod
    def _status_border(color: str) -> str:
        if color == COLOR_PASS:
            return "#badfca"
        if color == COLOR_FAIL:
            return "#f1bcbc"
        if color == COLOR_ERROR:
            return "#e6b5b5"
        return "#b8d9e3"

    def _clear_barcode_input(self) -> None:
        with QSignalBlocker(self.barcode_entry):
            self.barcode_entry.clear()
        self._set_verify_enabled_by_devices()

    def _append_log(self, message: str) -> None:
        if self._is_closing:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.appendPlainText(f"[{timestamp}] {message}")
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def _clear_logs(self) -> None:
        self.log_box.clear()
        self._append_log("Logs cleared.")

    def _focus_barcode_entry(self) -> None:
        self.barcode_entry.setFocus(Qt.OtherFocusReason)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._is_closing = True
        try:
            self.device_monitor.stop()
            event.accept()
        except Exception as exc:  # pylint: disable=broad-except
            QMessageBox.critical(self, "Shutdown Error", str(exc))
            event.accept()


def run_app() -> None:
    app = QApplication.instance() or QApplication([])
    window = SerialVerificationMainWindow()
    window.show()
    app.exec_()


__all__ = ["run_app", "SerialVerificationMainWindow"]
