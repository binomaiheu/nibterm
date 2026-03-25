from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import settings_keys as SK
from ..firmware.firmware_registry import FirmwareFile, FirmwareRegistry
from ..firmware.toolchain_schema import Device, FirmwareConfig, load_firmware_config
from ..firmware.upload_runner import UploadRunner, resolve_args
from ..logging.file_logger import FileLogger

logger = logging.getLogger(__name__)


class FirmwareWidget(QWidget):
    port_release_requested = Signal(str)
    upload_complete = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._config: FirmwareConfig | None = None
        self._firmware_files: list[FirmwareFile] = []
        self._runner = UploadRunner(self)
        self._upload_logger = FileLogger()
        self._pending_upload = False

        self._build_ui()
        self._connect_signals()

    # -- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Config file row
        config_row = QHBoxLayout()
        config_row.addWidget(QLabel("Config:"))
        self._config_path_label = QLabel("(none)")
        self._config_path_label.setMinimumWidth(200)
        config_row.addWidget(self._config_path_label, 1)
        self._browse_btn = QPushButton("Browse…")
        self._reload_btn = QPushButton("Reload")
        self._reload_btn.setEnabled(False)
        config_row.addWidget(self._browse_btn)
        config_row.addWidget(self._reload_btn)
        layout.addLayout(config_row)

        # Device selector
        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Device:"))
        self._device_combo = QComboBox()
        self._device_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        dev_row.addWidget(self._device_combo, 1)
        layout.addLayout(dev_row)

        # Firmware version selector
        fw_row = QHBoxLayout()
        fw_row.addWidget(QLabel("Firmware:"))
        self._firmware_combo = QComboBox()
        self._firmware_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        fw_row.addWidget(self._firmware_combo, 1)
        layout.addLayout(fw_row)

        # Port selector
        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)
        self._port_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        port_row.addWidget(self._port_combo, 1)
        self._refresh_ports_btn = QPushButton("Refresh")
        port_row.addWidget(self._refresh_ports_btn)
        layout.addLayout(port_row)

        # Action buttons
        btn_row = QHBoxLayout()
        self._upload_btn = QPushButton("Upload")
        self._upload_btn.setEnabled(False)
        self._upload_btn.setMinimumHeight(36)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setMinimumHeight(36)
        btn_row.addWidget(self._upload_btn)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Output display
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Monospace", 9))
        self._output.setMaximumBlockCount(5000)
        layout.addWidget(self._output, 1)

        # Bottom row
        bottom_row = QHBoxLayout()
        self._clear_btn = QPushButton("Clear")
        bottom_row.addWidget(self._clear_btn)
        bottom_row.addStretch()
        self._status_label = QLabel("Status: Idle")
        bottom_row.addWidget(self._status_label)
        layout.addLayout(bottom_row)

    def _connect_signals(self) -> None:
        self._browse_btn.clicked.connect(self.load_config_dialog)
        self._reload_btn.clicked.connect(self._reload_config)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        self._refresh_ports_btn.clicked.connect(self._refresh_ports)
        self._upload_btn.clicked.connect(self._on_upload_clicked)
        self._cancel_btn.clicked.connect(self._runner.cancel)
        self._clear_btn.clicked.connect(self._output.clear)

        self._runner.output_line.connect(self._on_output_line)
        self._runner.output_replace.connect(self._on_output_replace)
        self._runner.upload_started.connect(self._on_upload_started)
        self._runner.upload_finished.connect(self._on_upload_finished)

    # -- Config loading -----------------------------------------------------

    def load_config_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Firmware Config", "", "YAML files (*.yaml *.yml)"
        )
        if path:
            self._load_config(path)

    def _load_config(self, path: str) -> None:
        try:
            self._config = load_firmware_config(path)
        except Exception as e:
            self._append_error(f"Failed to load config: {e}")
            return

        self._config_path_label.setText(path)
        self._reload_btn.setEnabled(True)

        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        for dev in self._config.devices:
            self._device_combo.addItem(dev.label, dev.name)
        self._device_combo.blockSignals(False)

        # Restore last selected device
        settings = QSettings()
        last_dev = settings.value(SK.FIRMWARE_LAST_DEVICE, "")
        if last_dev:
            idx = self._device_combo.findData(last_dev)
            if idx >= 0:
                self._device_combo.setCurrentIndex(idx)

        self._on_device_changed(self._device_combo.currentIndex())
        self._refresh_ports()

        # Restore last port
        last_port = settings.value(SK.FIRMWARE_LAST_PORT, "")
        if last_port:
            idx = self._port_combo.findText(last_port)
            if idx >= 0:
                self._port_combo.setCurrentIndex(idx)

        settings.setValue(SK.FIRMWARE_CONFIG_PATH, path)
        self._upload_btn.setEnabled(True)

    def _reload_config(self) -> None:
        path = self._config_path_label.text()
        if path and path != "(none)":
            self._load_config(path)

    def restore_last_config(self) -> None:
        """Called by MainWindow on startup to restore last used config."""
        settings = QSettings()
        path = settings.value(SK.FIRMWARE_CONFIG_PATH, "")
        if path and Path(path).is_file():
            self._load_config(path)

    # -- Device / firmware scanning -----------------------------------------

    @Slot(int)
    def _on_device_changed(self, index: int) -> None:
        self._firmware_combo.clear()
        self._firmware_files = []

        dev = self._current_device()
        if not dev or not self._config:
            return

        folder = dev.firmware_folder or self._config.firmware_folder
        registry = FirmwareRegistry(folder)
        self._firmware_files = registry.scan(dev.file_glob, dev.version_pattern)
        for fw in self._firmware_files:
            display = f"v{fw.version}" if fw.version != "unknown" else fw.filename
            self._firmware_combo.addItem(f"{display}  ({fw.filename})")

        settings = QSettings()
        settings.setValue(SK.FIRMWARE_LAST_DEVICE, dev.name)

    def _current_device(self) -> Device | None:
        if not self._config:
            return None
        idx = self._device_combo.currentIndex()
        if 0 <= idx < len(self._config.devices):
            return self._config.devices[idx]
        return None

    def _current_firmware(self) -> FirmwareFile | None:
        idx = self._firmware_combo.currentIndex()
        if 0 <= idx < len(self._firmware_files):
            return self._firmware_files[idx]
        return None

    # -- Port management ----------------------------------------------------

    def _refresh_ports(self) -> None:
        current = self._port_combo.currentText()
        self._port_combo.clear()
        for info in QSerialPortInfo.availablePorts():
            self._port_combo.addItem(info.systemLocation())
        if current:
            idx = self._port_combo.findText(current)
            if idx >= 0:
                self._port_combo.setCurrentIndex(idx)

    # -- Upload flow --------------------------------------------------------

    @Slot()
    def _on_upload_clicked(self) -> None:
        dev = self._current_device()
        fw = self._current_firmware()
        port = self._port_combo.currentText().strip()

        if not dev:
            self._append_error("No device selected.")
            return
        if not fw:
            self._append_error("No firmware selected.")
            return
        if not port:
            self._append_error("No port specified.")
            return

        QSettings().setValue(SK.FIRMWARE_LAST_PORT, port)

        self._pending_upload = True
        self.port_release_requested.emit(port)

    def notify_port_released(self) -> None:
        """Called by MainWindow after the serial port has been released (or was not in use)."""
        if not self._pending_upload:
            return
        self._pending_upload = False

        dev = self._current_device()
        fw = self._current_firmware()
        port = self._port_combo.currentText().strip()
        if not dev or not fw or not port:
            return

        delay = dev.pre_upload_delay_ms
        if delay > 0:
            QTimer.singleShot(delay, lambda: self._start_upload(dev, fw, port))
        else:
            self._start_upload(dev, fw, port)

    def _start_upload(self, dev: Device, fw: FirmwareFile, port: str) -> None:
        args = resolve_args(dev.args, port, str(fw.path))
        self._append_info(
            f"Uploading {fw.filename} to {dev.label} on {port}"
        )
        self._append_info(f"Command: {dev.executable} {' '.join(args)}")

        # Start upload log if log_folder is configured
        if self._config and self._config.log_folder:
            log_dir = Path(self._config.log_folder)
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_name = f"upload_{dev.name}_{fw.version}_{timestamp}.log"
            self._upload_logger.start(log_dir / log_name)
            self._append_info(f"Logging to: {log_dir / log_name}")

        self._runner.start(dev.executable, args)

    @Slot()
    def _on_upload_started(self) -> None:
        self._upload_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._status_label.setText("Status: Uploading…")

    @Slot(int, str)
    def _on_upload_finished(self, exit_code: int, status: str) -> None:
        self._upload_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._upload_logger.stop()

        if exit_code == 0 and status == "normal":
            self._append_info("Upload completed successfully.")
            self._status_label.setText("Status: Success")
        else:
            self._append_error(
                f"Upload finished with exit code {exit_code} ({status})."
            )
            self._status_label.setText(f"Status: Failed (exit {exit_code})")

        self.upload_complete.emit()

    # -- Output handling ----------------------------------------------------

    @Slot(str)
    def _on_output_line(self, line: str) -> None:
        """A newline was received — move to the next line."""
        self._output.appendPlainText(line)
        if self._upload_logger.is_active():
            self._upload_logger.log_line(line)

    @Slot(str)
    def _on_output_replace(self, line: str) -> None:
        """Replace the last line with the fully resolved line content."""
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.movePosition(
            QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor
        )
        cursor.removeSelectedText()
        cursor.insertText(line)
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    def _append_info(self, text: str) -> None:
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#2196F3"))
        cursor.insertText(f"[nibterm] {text}\n", fmt)
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()
        if self._upload_logger.is_active():
            self._upload_logger.log_line(f"[nibterm] {text}")

    def _append_error(self, text: str) -> None:
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#F44336"))
        cursor.insertText(f"[nibterm] {text}\n", fmt)
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    # -- Cleanup ------------------------------------------------------------

    def cancel_if_running(self) -> None:
        """Called by MainWindow on close to ensure no orphaned processes."""
        if self._runner.is_running():
            self._runner.cancel()
        self._upload_logger.stop()
