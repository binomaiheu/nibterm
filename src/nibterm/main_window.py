from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
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
from .ui.dashboard_window import DashboardWindow
from .version import __version__


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

        self._plot_config = PlotConfig.from_qsettings(self._settings)
        self._dashboard_window = DashboardWindow(self._settings, self._plot_config, self)

        self._tabs = QTabWidget()
        self._terminal_tab_index = self._tabs.addTab(terminal_widget, "Terminal")
        self._dashboard_tab_index = self._tabs.addTab(self._dashboard_window, "Dashboard")
        self.setCentralWidget(self._tabs)

        self._command_toolbar = CommandToolbar(self)
        self._command_toolbar.setObjectName("CommandsToolbar")
        self._command_toolbar.command_requested.connect(self._send_command)
        self._command_toolbar.preset_loaded.connect(self._store_last_preset_path)
        self.addToolBar(Qt.ToolBarArea.RightToolBarArea, self._command_toolbar)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_icon = QLabel()
        self._status_label = QLabel("Disconnected")
        self._status_log_label = QLabel("")
        self._status.addWidget(self._status_icon)
        self._status.addWidget(self._status_label)
        self._status.addWidget(QLabel(" | "))
        self._status.addWidget(self._status_log_label)
        self._reconnecting = False
        self._set_status_state("disconnected")

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
        self._action_connect_toggle = QAction("Connect", self)
        self._action_connect_toggle.setCheckable(True)
        self._action_quit = QAction("Quit", self)
        self._action_quit.triggered.connect(self.close)
        self._action_connect_toggle.triggered.connect(self._toggle_connection)
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
        self._action_plot_settings = QAction("Data Pipeline...", self)
        self._action_plot_settings.triggered.connect(self._open_plot_settings)
        view_menu.addAction(self._action_plot_settings)
        self._action_clear_plot = QAction("Clear plot", self)
        self._action_clear_plot.triggered.connect(self._clear_plot)
        view_menu.addAction(self._action_clear_plot)

        help_menu = menu.addMenu("Help")
        self._action_about = QAction("About", self)
        self._action_about.triggered.connect(self._show_about)
        help_menu.addAction(self._action_about)

        self._plot_toolbar = self.addToolBar("Plot")
        self._plot_toolbar.setObjectName("PlotToolbar")
        self._plot_toolbar.setMovable(False)

        file_menu.addAction(self._action_connect_toggle)
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
        self._connection_toolbar.addAction(self._action_connect_toggle)

        self._action_connect_toggle.setChecked(False)

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
            self._action_connect_toggle.setChecked(False)
            return
        opened = self._port_manager.open(self._serial_settings)
        if not opened:
            QMessageBox.critical(
                self, "Serial", "Failed to open serial port."
            )
            self._action_connect_toggle.setChecked(False)

    def _toggle_connection(self, checked: bool) -> None:
        if checked:
            self._connect_serial()
        else:
            self._disconnect_serial()

    @Slot()
    def _disconnect_serial(self) -> None:
        self._port_manager.close()

    @Slot(bool)
    def _on_connection_changed(self, connected: bool) -> None:
        self._action_connect_toggle.setChecked(connected)
        self._action_connect_toggle.setText("Disconnect" if connected else "Connect")
        if connected:
            self._status_label.setText(self._connection_status_text())
            self._set_status_state("connected")
        else:
            self._status_label.setText("Disconnected")
            self._set_status_state("disconnected")
        if connected and self._reconnecting:
            self._console.append_status_message(
                "Device reconnected.",
                self._serial_settings.timestamp_prefix,
                "#0d47a1",
            )
            self._reconnecting = False

    @Slot(str)
    def _on_serial_error(self, message: str) -> None:
        self._status_label.setText(f"Error: {message}")

    @Slot(bool)
    def _on_reconnecting(self, reconnecting: bool) -> None:
        if reconnecting:
            port = self._serial_settings.port_name or "device"
            self._status_label.setText(f"Waiting for {port}")
            self._set_status_state("waiting")
            if not self._reconnecting:
                self._console.append_status_message(
                    "Waiting for device connection...",
                    self._serial_settings.timestamp_prefix,
                    "#0d47a1",
                )
                self._reconnecting = True
        else:
            if self._port_manager.is_open():
                self._status_label.setText(self._connection_status_text())
                self._set_status_state("connected")
            else:
                self._status_label.setText("Disconnected")
                self._set_status_state("disconnected")

    def _set_status_state(self, state: str) -> None:
        colors = {
            "connected": "#2e7d32",
            "waiting": "#f9a825",
            "disconnected": "#c62828",
        }
        color = colors.get(state, "#9e9e9e")
        self._status_icon.setStyleSheet(
            f"background-color: {color}; border-radius: 6px;"
        )
        self._status_icon.setFixedSize(12, 12)

    def _show_about(self) -> None:
        version_text = __version__
        if version_text == "unknown":
            version_text = "unknown (no git info)"
        QMessageBox.about(
            self,
            "About nibterm",
            f"nibterm\nVersion: {version_text}",
        )

    def _connection_status_text(self) -> str:
        s = self._serial_settings
        return (
            f"Connected ({s.port_name}, {s.baud_rate}, "
            f"{s.data_bits.name}, {s.parity.name}, {s.stop_bits.name}, "
            f"{s.flow_control.name})"
        )

    @Slot(bytes)
    def _on_data_received(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        lines = self._console.append_data(text, self._serial_settings.timestamp_prefix)
        for line in lines:
            if self._dashboard_window:
                self._dashboard_window.handle_line(line)
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
        dialog = QFileDialog(
            self,
            "Log file",
            self._settings.value("logging/last_path", "", str),
            "Text files (*.txt);;All files (*)",
        )
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.DontConfirmOverwrite, True)
        dialog.setLabelText(QFileDialog.DialogLabel.Accept, "Append")
        button_box = dialog.findChild(QDialogButtonBox)
        mode_holder = {"mode": "a"}
        replace_button = None
        if button_box:
            append_button = button_box.button(QDialogButtonBox.StandardButton.Save)
            if append_button:
                append_button.clicked.connect(lambda: mode_holder.update(mode="a"))
            replace_button = button_box.addButton(
                "Replace",
                QDialogButtonBox.ButtonRole.AcceptRole,
            )
            replace_button.clicked.connect(lambda: mode_holder.update(mode="w"))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        files = dialog.selectedFiles()
        if not files:
            return
        path = files[0]
        self._file_logger.start(Path(path), mode=mode_holder["mode"])
        self._settings.setValue("logging/last_path", path)
        self._action_log_start.setEnabled(False)
        self._action_log_stop.setEnabled(True)
        self._status_log_label.setText(f"Logging to {path}")

    def _stop_logging(self) -> None:
        self._file_logger.stop()
        self._action_log_start.setEnabled(True)
        self._action_log_stop.setEnabled(False)
        self._status_log_label.setText("Logging stopped")

    def _open_plot_settings(self) -> None:
        dialog = PlotSettingsDialog(self)
        dialog.load(self._plot_config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._plot_config = dialog.config()
            if self._dashboard_window:
                self._dashboard_window.apply_config(self._plot_config)
            self._save_settings()

    def _clear_plot(self) -> None:
        if self._dashboard_window:
            self._dashboard_window.clear_plots()

    def _save_settings(self) -> None:
        self._serial_settings.to_qsettings(self._settings)
        self._appearance_settings.to_qsettings(self._settings)
        self._plot_config.to_qsettings(self._settings)
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/state", self.saveState())
        self._settings.setValue("view/tab", self._tabs.currentIndex())
        if self._dashboard_window:
            self._dashboard_window.save_state()

    def _restore_window_state(self) -> None:
        geometry = self._settings.value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self._settings.value("window/state")
        if state:
            self.restoreState(state)
        tab_index = self._settings.value("view/tab")
        if tab_index is not None:
            try:
                self._tabs.setCurrentIndex(int(tab_index))
            except (TypeError, ValueError):
                pass
        if self._dashboard_window:
            self._dashboard_window.restore_state()


    def _store_last_preset_path(self, path: str) -> None:
        self._settings.setValue("commands/last_path", path)

    def _restore_last_preset(self) -> None:
        path = self._settings.value("commands/last_path", "", str)
        if path:
            try:
                self._command_toolbar.load_preset_from_path(path)
            except Exception:
                self._settings.remove("commands/last_path")
