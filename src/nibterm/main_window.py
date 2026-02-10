from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .logging.file_logger import FileLogger
from .serial.port_manager import PortManager
from .serial.settings import AppearanceSettings, SerialSettings
from .ui.console import ConsoleWidget
from .ui.plot_panel import PlotConfig, PlotPanel
from .ui.plot_settings_dialog import PlotSettingsDialog
from .ui.settings_dialog import SettingsDialog
from .ui.command_toolbar import CommandToolbar
from .ui.plot_window import PlotWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        QCoreApplication.setOrganizationName("nibsoft")
        QCoreApplication.setApplicationName("nibterm")

        self.setWindowTitle("nibterm - a vibe coded serial terminal application")

        self._settings = QSettings()
        self._serial_settings = SerialSettings.from_qsettings(self._settings)
        self._appearance_settings = AppearanceSettings.from_qsettings(self._settings)
        if self._appearance_settings.background_color.lower() in ("#000000", "black"):
            text_color = self._appearance_settings.text_color.lower()
            if text_color in ("#00ff00", "green"):
                self._appearance_settings.background_color = "#fff7cc"
                self._appearance_settings.text_color = "#000000"

        self._port_manager = PortManager(self)
        self._port_manager.data_received.connect(self._on_data_received)
        self._port_manager.connection_changed.connect(self._on_connection_changed)
        self._port_manager.error.connect(self._on_serial_error)
        self._port_manager.reconnecting.connect(self._on_reconnecting)

        self._file_logger = FileLogger()

        self._settings_dialog = SettingsDialog(self)
        self._settings_dialog.load(self._serial_settings, self._appearance_settings)

        self._console = ConsoleWidget()
        self._console.set_appearance(
            self._appearance_settings.font_family,
            self._appearance_settings.font_size,
            self._appearance_settings.background_color,
            self._appearance_settings.text_color,
        )

        self._input_line = QLineEdit()
        self._input_line.setPlaceholderText("Type and press Enter to send")
        self._send_button = QPushButton("Send")
        self._send_button.clicked.connect(self._send_input)
        self._input_line.returnPressed.connect(self._send_input_if_enabled)

        input_row = QHBoxLayout()
        input_row.addWidget(self._input_line)
        input_row.addWidget(self._send_button)

        terminal_layout = QVBoxLayout()
        terminal_layout.addWidget(self._console)
        terminal_layout.addLayout(input_row)

        terminal_widget = QWidget()
        terminal_widget.setLayout(terminal_layout)

        self.setCentralWidget(terminal_widget)

        self._command_toolbar = CommandToolbar(self)
        self._command_toolbar.setObjectName("CommandsToolbar")
        self._command_toolbar.command_requested.connect(self._send_command)
        self._command_toolbar.preset_loaded.connect(self._store_last_preset_path)
        self.addToolBar(Qt.ToolBarArea.RightToolBarArea, self._command_toolbar)

        self._plot_config = PlotConfig.from_qsettings(self._settings)
        self._plot_panel: PlotPanel | None = None
        self._plot_window: PlotWindow | None = None

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_label = QLabel("Disconnected")
        self._status.addWidget(self._status_label)

        self._create_actions()
        self._restore_window_state()
        self._restore_last_preset()

        self._port_manager.set_auto_reconnect(self._serial_settings.auto_reconnect)

    def closeEvent(self, event) -> None:
        self._save_settings()
        if self._file_logger.is_active():
            self._file_logger.stop()
        super().closeEvent(event)

    def _create_actions(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        self._action_connect = QAction("Connect", self)
        self._action_disconnect = QAction("Disconnect", self)
        self._action_quit = QAction("Quit", self)
        self._action_quit.triggered.connect(self.close)
        self._action_connect.triggered.connect(self._connect_serial)
        self._action_disconnect.triggered.connect(self._disconnect_serial)
        tools_menu = menu.addMenu("Tools")
        self._action_settings = QAction("Configure...", self)
        self._action_settings.triggered.connect(self._open_settings)
        self._action_clear = QAction("Clear terminal", self)
        self._action_clear.triggered.connect(self._console.clear)
        self._action_log_start = QAction("Start logging...", self)
        self._action_log_stop = QAction("Stop logging", self)
        self._action_log_stop.setEnabled(False)
        self._action_log_start.triggered.connect(self._start_logging)
        self._action_log_stop.triggered.connect(self._stop_logging)
        tools_menu.addAction(self._action_settings)
        tools_menu.addAction(self._action_clear)
        tools_menu.addSeparator()
        tools_menu.addAction(self._action_log_start)
        tools_menu.addAction(self._action_log_stop)

        view_menu = menu.addMenu("View")
        self._action_plot_settings = QAction("Plot settings...", self)
        self._action_plot_settings.triggered.connect(self._open_plot_settings)
        view_menu.addAction(self._action_plot_settings)
        self._action_clear_plot = QAction("Clear plot", self)
        self._action_clear_plot.triggered.connect(self._clear_plot)
        view_menu.addAction(self._action_clear_plot)

        self._plot_toolbar = self.addToolBar("Plot")
        self._plot_toolbar.setObjectName("PlotToolbar")
        self._plot_toolbar.setMovable(False)
        self._action_show_plot = QAction("Plot window", self)
        self._action_show_plot.setCheckable(True)
        self._action_show_plot.triggered.connect(self._toggle_plot_panel)
        self._plot_toolbar.addAction(self._action_show_plot)

        file_menu.addAction(self._action_connect)
        file_menu.addAction(self._action_disconnect)
        file_menu.addSeparator()
        self._action_load_preset = QAction("Load preset...", self)
        self._action_clear_preset = QAction("Clear preset", self)
        self._action_load_preset.triggered.connect(
            self._command_toolbar.load_preset_via_dialog
        )
        self._action_clear_preset.triggered.connect(
            self._command_toolbar.clear_preset
        )
        file_menu.addAction(self._action_load_preset)
        file_menu.addAction(self._action_clear_preset)
        file_menu.addSeparator()
        file_menu.addAction(self._action_quit)

        self._connection_toolbar = self.addToolBar("Connection")
        self._connection_toolbar.setObjectName("ConnectionToolbar")
        self._connection_toolbar.setMovable(False)
        self._connection_toolbar.addAction(self._action_connect)
        self._connection_toolbar.addAction(self._action_disconnect)

        self._action_disconnect.setEnabled(False)

    @Slot()
    def _open_settings(self) -> None:
        self._settings_dialog.refresh_ports()
        self._settings_dialog.load(self._serial_settings, self._appearance_settings)
        if self._settings_dialog.exec() == QDialog.DialogCode.Accepted:
            self._serial_settings = self._settings_dialog.serial_settings()
            self._appearance_settings = self._settings_dialog.appearance_settings()
            self._apply_appearance()
            self._port_manager.set_auto_reconnect(self._serial_settings.auto_reconnect)
            if self._port_manager.is_open():
                self._port_manager.close()
                self._connect_serial()
            self._save_settings()

    def _apply_appearance(self) -> None:
        self._console.set_appearance(
            self._appearance_settings.font_family,
            self._appearance_settings.font_size,
            self._appearance_settings.background_color,
            self._appearance_settings.text_color,
        )

    @Slot()
    def _connect_serial(self) -> None:
        if not self._serial_settings.port_name:
            QMessageBox.warning(self, "Serial", "No serial port selected.")
            return
        opened = self._port_manager.open(self._serial_settings)
        if not opened:
            QMessageBox.critical(
                self, "Serial", "Failed to open serial port."
            )

    @Slot()
    def _disconnect_serial(self) -> None:
        self._port_manager.close()

    @Slot(bool)
    def _on_connection_changed(self, connected: bool) -> None:
        self._action_connect.setEnabled(not connected)
        self._action_disconnect.setEnabled(connected)
        status = "Connected" if connected else "Disconnected"
        self._status_label.setText(status)

    @Slot(str)
    def _on_serial_error(self, message: str) -> None:
        self._status_label.setText(f"Error: {message}")

    @Slot(bool)
    def _on_reconnecting(self, reconnecting: bool) -> None:
        if reconnecting:
            self._status_label.setText("Waiting for connection...")
        else:
            if self._port_manager.is_open():
                self._status_label.setText("Connected")
            else:
                self._status_label.setText("Disconnected")

    @Slot(bytes)
    def _on_data_received(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        lines = self._console.append_data(text, self._serial_settings.timestamp_prefix)
        for line in lines:
            if self._plot_panel and self._action_show_plot.isChecked():
                self._plot_panel.handle_line(line)
            if self._file_logger.is_active():
                self._file_logger.log_line(line)

    def _send_input_if_enabled(self) -> None:
        if self._serial_settings.send_on_enter:
            self._send_input()

    def _send_input(self) -> None:
        raw = self._input_line.text()
        if not raw:
            return
        payload = f"{raw}{self._serial_settings.line_ending}"
        self._port_manager.write(payload.encode("utf-8"))
        if self._serial_settings.local_echo:
            self._console.append_text_colored(f"> {raw}", "#d32f2f")
        self._input_line.clear()

    def _send_command(self, command: str) -> None:
        if not command:
            return
        self._port_manager.write(command.encode("utf-8"))
        if self._serial_settings.local_echo:
            self._console.append_text_colored(f"> {command.rstrip()}", "#d32f2f")

    def _start_logging(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Log file",
            self._settings.value("logging/last_path", "", str),
            "Text files (*.txt);;All files (*)",
        )
        if not path:
            return
        self._file_logger.start(Path(path))
        self._settings.setValue("logging/last_path", path)
        self._action_log_start.setEnabled(False)
        self._action_log_stop.setEnabled(True)
        self._status_label.setText(f"Logging to {path}")

    def _stop_logging(self) -> None:
        self._file_logger.stop()
        self._action_log_start.setEnabled(True)
        self._action_log_stop.setEnabled(False)
        self._status_label.setText("Logging stopped")

    def _toggle_plot_panel(self, checked: bool) -> None:
        if checked:
            self._ensure_plot_window()
            if self._plot_window:
                self._plot_window.show()
            if self._plot_panel:
                self._plot_panel.set_enabled(True)
        else:
            if self._plot_panel:
                self._plot_panel.set_enabled(False)
            if self._plot_window:
                self._plot_window.hide()
        self._settings.setValue("view/plot_visible", checked)

    def _open_plot_settings(self) -> None:
        dialog = PlotSettingsDialog(self)
        dialog.load(self._plot_config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._plot_config = dialog.config()
            if self._plot_panel:
                self._plot_panel.set_config(self._plot_config)
                self._plot_panel.set_enabled(self._action_show_plot.isChecked())
            self._save_settings()

    def _clear_plot(self) -> None:
        if self._plot_panel:
            self._plot_panel.clear()

    def _ensure_plot_window(self) -> None:
        if self._plot_panel is None:
            self._plot_panel = PlotPanel()
            self._plot_panel.set_config(self._plot_config)
            self._plot_panel.set_enabled(self._action_show_plot.isChecked())
        if self._plot_window is None:
            self._plot_window = PlotWindow(self._plot_panel, self._settings, self)
            self._plot_window.window_closed.connect(self._on_plot_window_closed)
            self._plot_window.restore_state()

    def _on_plot_window_closed(self) -> None:
        self._action_show_plot.setChecked(False)
        if self._plot_panel:
            self._plot_panel.set_enabled(False)
        self._settings.setValue("view/plot_visible", False)

    def _save_settings(self) -> None:
        self._serial_settings.to_qsettings(self._settings)
        self._appearance_settings.to_qsettings(self._settings)
        self._plot_config.to_qsettings(self._settings)
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/state", self.saveState())
        self._settings.setValue(
            "view/plot_visible",
            self._action_show_plot.isChecked(),
        )
        if self._plot_window:
            self._plot_window.save_state()

    def _restore_window_state(self) -> None:
        geometry = self._settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self._settings.value("window/state")
        if state:
            self.restoreState(state)
        visible = self._settings.value("view/plot_visible", False, bool)
        self._action_show_plot.setChecked(visible)
        if visible:
            self._ensure_plot_window()
            if self._plot_window:
                self._plot_window.show()
        else:
            if self._plot_window:
                self._plot_window.hide()

    def _store_last_preset_path(self, path: str) -> None:
        self._settings.setValue("commands/last_path", path)

    def _restore_last_preset(self) -> None:
        path = self._settings.value("commands/last_path", "", str)
        if path:
            try:
                self._command_toolbar.load_preset_from_path(path)
            except Exception:
                self._settings.remove("commands/last_path")
