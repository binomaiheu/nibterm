from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from PySide6.QtCore import QCoreApplication, QSettings, Qt, Slot
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
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
    QSplitter,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from .config import settings_keys as SK
from .config.migration import migrate_settings
from .config.plot_config import PlotConfig
from .data.variable_manager import VariableManager
from .logging.file_logger import FileLogger
from .mqtt import MQTTManager, MQTTSettings
from .serial.port_manager import PortManager
from .serial.settings import AppearanceSettings, SerialSettings
from .ui.console import ConsoleWidget
from .ui.plot_panel import PlotPanel
from .ui.serial_parser_dialog import SerialParserDialog
from .ui.settings_dialog import SettingsDialog
from .ui.command_toolbar import CommandToolbar
from .ui.dashboard_window import DashboardWindow
from .ui.mqtt_monitor import MQTTMonitorWidget
from .ui.mqtt_settings_dialog import MQTTSettingsDialog
from .ui.serial_plot_panel import SerialPlotPanel
from .ui.variable_dialog import VariablesDialog
from .ui.help_window import HelpWindow
from .version import __version__

# Resolve static dir: repo root when running from source, or package static if present
_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
if not (_STATIC_DIR / "connected.svg").exists():
    _STATIC_DIR = Path(__file__).resolve().parent / "static"


def _connect_icon() -> QIcon:
    path = _STATIC_DIR / "connected.svg"
    if path.exists():
        return QIcon(str(path))
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)


def _disconnect_icon() -> QIcon:
    path = _STATIC_DIR / "disconnected.svg"
    if path.exists():
        return QIcon(str(path))
    return QApplication.style().standardIcon(
        QStyle.StandardPixmap.SP_TitleBarCloseButton
    )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        QCoreApplication.setOrganizationName("nibsoft")
        QCoreApplication.setApplicationName("nibterm")

        self.setWindowTitle("nibterm - a vibe coded serial IoT device terminal")

        self._settings = QSettings()
        migrate_settings(self._settings)
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
        self._settings_dialog.settings_applied.connect(self._apply_settings)

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

        # -- Variable Manager (central source of truth) --
        self._variable_manager = VariableManager(self._settings, self)

        self._plot_config = PlotConfig.from_qsettings(self._settings)
        self._dashboard_window = DashboardWindow(
            self._settings,
            self._plot_config,
            variable_list_fn=self._variable_manager.get_variable_list,
            parent=self,
        )
        self._variable_manager.variables_changed.connect(
            self._dashboard_window.on_variables_changed
        )

        self._mqtt_settings = MQTTSettings.from_qsettings(self._settings)
        self._mqtt_manager = MQTTManager(self)
        self._mqtt_manager.message_received.connect(self._on_mqtt_message)
        self._mqtt_manager.connection_changed.connect(self._on_mqtt_connection_changed)
        self._mqtt_manager.error.connect(self._on_mqtt_error)
        self._mqtt_settings_dialog = MQTTSettingsDialog(self)
        self._mqtt_monitor_widget = MQTTMonitorWidget(self._variable_manager, self)
        self._mqtt_monitor_widget.set_values_callback(self._on_mqtt_plot_values)

        self._serial_plot_panel = SerialPlotPanel(self._variable_manager, self)
        terminal_widget.layout().addWidget(self._serial_plot_panel)

        self._tabs = QTabWidget()
        self._terminal_tab_index = self._tabs.addTab(terminal_widget, "Terminal")
        self._mqtt_tab_index = self._tabs.addTab(self._mqtt_monitor_widget, "MQTT")
        self._dashboard_tab_index = self._tabs.addTab(self._dashboard_window, "Dashboard")
        self._tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._command_toolbar = CommandToolbar(self)
        self._command_toolbar.setObjectName("CommandsToolbar")
        self._command_toolbar.command_requested.connect(self._send_command)
        self._command_toolbar.preset_loaded.connect(self._store_last_preset_path)
        self._command_toolbar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.addWidget(self._tabs)
        self._main_splitter.addWidget(self._command_toolbar)
        self._main_splitter.setStretchFactor(0, 3)
        self._main_splitter.setStretchFactor(1, 1)
        self._main_splitter.setChildrenCollapsible(False)
        self.setCentralWidget(self._main_splitter)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status_icon = QLabel()
        self._status_label = QLabel("Disconnected")
        self._status.addWidget(self._status_icon)
        self._status.addWidget(self._status_label)
        self._status.addWidget(QLabel(" | "))
        self._status_mqtt_icon = QLabel()
        self._status_mqtt_label = QLabel("MQTT: Disconnected")
        self._status.addWidget(self._status_mqtt_icon)
        self._status.addWidget(self._status_mqtt_label)
        self._status.addWidget(QLabel(" | "))
        self._status_log_label = QLabel("")
        self._status.addWidget(self._status_log_label)
        self._reconnecting = False
        self._set_status_state("disconnected")
        self._set_mqtt_status_state("disconnected")
        self._log_path: Path | None = None

        self._create_actions()
        self._restore_window_state()
        self._restore_last_preset()

        self._port_manager.set_auto_reconnect(self._serial_settings.auto_reconnect)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_settings()
        if self._file_logger.is_active():
            self._file_logger.stop()
        if self._mqtt_manager.is_connected():
            self._mqtt_manager.disconnect_()
        super().closeEvent(event)

    def _create_actions(self) -> None:
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        self._action_connect_toggle = QAction("Serial Disconnected", self)
        self._action_connect_toggle.setIcon(_disconnect_icon())
        self._action_connect_toggle.setCheckable(True)
        self._action_quit = QAction("Quit", self)
        self._action_quit.triggered.connect(self.close)
        self._action_connect_toggle.triggered.connect(self._toggle_connection)
        serial_menu = menu.addMenu("Serial")
        self._action_settings = QAction("Configure...", self)
        self._action_settings.setMenuRole(QAction.MenuRole.NoRole)
        self._action_settings.triggered.connect(self._open_settings)
        self._action_parser = QAction("Parser...", self)
        self._action_parser.setMenuRole(QAction.MenuRole.NoRole)
        self._action_parser.triggered.connect(self._open_serial_parser)
        self._action_clear = QAction("Clear terminal", self)
        self._action_clear.triggered.connect(self._console.clear)
        self._action_log_start = QAction("Start logging...", self)
        self._action_log_stop = QAction("Stop logging", self)
        self._action_log_stop.setEnabled(False)
        self._action_log_start.triggered.connect(self._start_logging)
        self._action_log_stop.triggered.connect(self._stop_logging)
        serial_menu.addAction(self._action_settings)
        serial_menu.addAction(self._action_parser)
        serial_menu.addAction(self._action_clear)
        serial_menu.addSeparator()
        serial_menu.addAction(self._action_log_start)
        serial_menu.addAction(self._action_log_stop)

        mqtt_menu = menu.addMenu("MQTT")
        self._action_mqtt_settings = QAction("Configure...", self)
        self._action_mqtt_settings.setMenuRole(QAction.MenuRole.NoRole)
        self._action_mqtt_settings.triggered.connect(self._open_mqtt_settings)
        mqtt_menu.addAction(self._action_mqtt_settings)

        # -- Variables menu --
        variables_menu = menu.addMenu("Variables")
        self._action_manage_variables = QAction("Manage Variables...", self)
        self._action_manage_variables.triggered.connect(self._open_variables_dialog)
        variables_menu.addAction(self._action_manage_variables)

        view_menu = menu.addMenu("Dashboard")
        view_menu.addSeparator()
        self._action_add_plot = QAction("Add plot", self)
        self._action_remove_plot = QAction("Remove plot", self)
        self._action_setup_plot = QAction("Setup plot...", self)
        self._action_clear_plot = QAction("Clear plot", self)
        self._action_add_plot.triggered.connect(self._add_plot)
        self._action_remove_plot.triggered.connect(self._remove_plot)
        self._action_setup_plot.triggered.connect(self._setup_plot)
        self._action_clear_plot.triggered.connect(self._clear_plot)
        view_menu.addAction(self._action_add_plot)
        view_menu.addAction(self._action_remove_plot)
        view_menu.addAction(self._action_setup_plot)
        view_menu.addAction(self._action_clear_plot)
        view_menu.addSeparator()
        self._action_tile_plots = QAction("Tile plots", self)
        self._action_cascade_plots = QAction("Cascade plots", self)
        self._action_tile_plots.triggered.connect(self._tile_plots)
        self._action_cascade_plots.triggered.connect(self._cascade_plots)
        view_menu.addAction(self._action_tile_plots)
        view_menu.addAction(self._action_cascade_plots)

        help_menu = menu.addMenu("Help")
        self._action_help = QAction("Help", self)
        self._action_help.triggered.connect(self._show_help)
        self._action_about = QAction("About", self)
        self._action_about.triggered.connect(self._show_about)
        help_menu.addAction(self._action_help)
        help_menu.addAction(self._action_about)

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
        connect_btn = self._connection_toolbar.widgetForAction(self._action_connect_toggle)
        if connect_btn:
            connect_btn.setMinimumHeight(40)
            connect_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._action_mqtt_connect_toggle = QAction("MQTT Disconnected", self)
        self._action_mqtt_connect_toggle.setIcon(_disconnect_icon())
        self._action_mqtt_connect_toggle.setCheckable(True)
        self._action_mqtt_connect_toggle.triggered.connect(self._toggle_mqtt_connection)
        self._connection_toolbar.addAction(self._action_mqtt_connect_toggle)
        mqtt_btn = self._connection_toolbar.widgetForAction(self._action_mqtt_connect_toggle)
        if mqtt_btn:
            mqtt_btn.setMinimumHeight(40)
            mqtt_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self._action_connect_toggle.setChecked(False)
        self._action_mqtt_connect_toggle.setChecked(False)

    @Slot()
    def _open_settings(self) -> None:
        self._settings_dialog.refresh_ports()
        self._settings_dialog.load(
            self._serial_settings,
            self._appearance_settings,
        )
        if self._settings_dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_settings(
                self._settings_dialog.serial_settings(),
                self._settings_dialog.appearance_settings(),
            )

    @Slot()
    def _open_serial_parser(self) -> None:
        """Open the Serial parser dialog (CSV / JSON)."""
        dialog = SerialParserDialog(
            self._variable_manager.serial_config,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._variable_manager.set_serial_config(dialog.config())

    def _apply_appearance(self) -> None:
        self._console.set_appearance(
            self._appearance_settings.font_family,
            self._appearance_settings.font_size,
            self._appearance_settings.background_color,
            self._appearance_settings.text_color,
        )

    def _apply_settings(
        self,
        serial_settings: SerialSettings,
        appearance_settings: AppearanceSettings,
    ) -> None:
        self._serial_settings = serial_settings
        self._appearance_settings = appearance_settings
        self._apply_appearance()
        self._port_manager.set_auto_reconnect(self._serial_settings.auto_reconnect)
        if self._port_manager.is_open():
            self._port_manager.close()
            self._connect_serial()
        self._save_settings()

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
        self._action_connect_toggle.setText(
            "Serial Connected" if connected else "Serial Disconnected"
        )
        self._action_connect_toggle.setIcon(
            _connect_icon() if connected else _disconnect_icon()
        )
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

    def _set_mqtt_status_state(self, state: str) -> None:
        colors = {
            "connected": "#2e7d32",
            "disconnected": "#c62828",
        }
        color = colors.get(state, "#c62828")
        self._status_mqtt_icon.setStyleSheet(
            f"background-color: {color}; border-radius: 6px;"
        )
        self._status_mqtt_icon.setFixedSize(12, 12)
        self._status_mqtt_label.setText(
            "MQTT: Connected" if state == "connected" else "MQTT: Disconnected"
        )

    @Slot(str, bytes)
    def _on_mqtt_message(self, topic: str, payload: bytes) -> None:
        self._mqtt_monitor_widget.on_message_received(topic, payload)

    def _on_mqtt_plot_values(self, values_by_name: dict[str, float]) -> None:
        """Update MQTT values via VariableManager and push to dashboard."""
        all_values, updated_names = self._variable_manager.process_mqtt_values(values_by_name)
        if self._dashboard_window and updated_names:
            self._dashboard_window.handle_values(all_values, updated_names=updated_names)

    def _open_mqtt_settings(self) -> None:
        self._mqtt_settings_dialog.load(self._mqtt_settings)
        if self._mqtt_settings_dialog.exec() == QDialog.DialogCode.Accepted:
            self._mqtt_settings = self._mqtt_settings_dialog.settings()
            self._mqtt_settings.to_qsettings(self._settings)

    def _toggle_mqtt_connection(self, checked: bool) -> None:
        if checked:
            self._mqtt_settings = MQTTSettings.from_qsettings(self._settings)
            if self._mqtt_manager.connect_(self._mqtt_settings):
                self._action_mqtt_connect_toggle.setText("MQTT Connected")
                self._action_mqtt_connect_toggle.setIcon(_connect_icon())
            else:
                self._action_mqtt_connect_toggle.setChecked(False)
        else:
            self._mqtt_manager.disconnect_()
            self._action_mqtt_connect_toggle.setText("MQTT Disconnected")
            self._action_mqtt_connect_toggle.setIcon(_disconnect_icon())

    def _on_mqtt_connection_changed(self, connected: bool) -> None:
        self._action_mqtt_connect_toggle.setChecked(connected)
        self._action_mqtt_connect_toggle.setText(
            "MQTT Connected" if connected else "MQTT Disconnected"
        )
        self._action_mqtt_connect_toggle.setIcon(
            _connect_icon() if connected else _disconnect_icon()
        )
        self._set_mqtt_status_state("connected" if connected else "disconnected")

    def _on_mqtt_error(self, message: str) -> None:
        QMessageBox.warning(self, "MQTT", message)

    def _show_help(self) -> None:
        win = HelpWindow(self)
        win.setWindowModality(Qt.WindowModality.NonModal)
        win.show()

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
        has_serial_vars = any(
            v.source == "serial" for v in self._variable_manager.variables
        )
        for line in lines:
            if self._dashboard_window and has_serial_vars:
                all_values, updated = self._variable_manager.process_serial_line(line)
                if updated:
                    self._dashboard_window.handle_values(all_values, updated_names=updated)
            if self._file_logger.is_active():
                self._file_logger.log_line(line)
                self._update_log_status()
        if lines:
            self._variable_manager.set_last_serial_line(lines[-1])

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
        self._log_path = Path(path)
        self._settings.setValue("logging/last_path", path)
        self._action_log_start.setEnabled(False)
        self._action_log_stop.setEnabled(True)
        self._update_log_status()

    def _stop_logging(self) -> None:
        self._file_logger.stop()
        self._action_log_start.setEnabled(True)
        self._action_log_stop.setEnabled(False)
        self._status_log_label.setText("Logging stopped")
        self._log_path = None

    def _update_log_status(self) -> None:
        if not self._file_logger.is_active() or not self._log_path:
            return
        size = self._file_logger.size_bytes()
        self._status_log_label.setText(
            f"Logging to {self._log_path} ({self._format_bytes(size)})"
        )

    @staticmethod
    def _format_bytes(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.0f} {unit}"
            size /= 1024
        return f"{size:.0f} PB"

    def _open_variables_dialog(self) -> None:
        """Open the unified Variables dialog."""
        dialog = VariablesDialog(
            self._variable_manager.variables,
            self._variable_manager.serial_config,
            get_values=lambda: self._variable_manager.get_values(),
            values_updated_signal=self._variable_manager.values_updated,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._variable_manager.set_variables(dialog.variables())
            # Refresh MQTT monitor table to stay in sync
            self._mqtt_monitor_widget.refresh_from_manager()

    def _clear_plot(self) -> None:
        if not self._dashboard_window or not self._dashboard_window.has_active_plot():
            QMessageBox.warning(self, "Plot", "No plot is selected.")
            return
        self._dashboard_window.clear_active_plot()

    def _add_plot(self) -> None:
        if self._dashboard_window:
            self._dashboard_window.add_plot()

    def _remove_plot(self) -> None:
        if not self._dashboard_window or not self._dashboard_window.has_active_plot():
            QMessageBox.warning(self, "Plot", "No plot is selected.")
            return
        self._dashboard_window.remove_plot()

    def _setup_plot(self) -> None:
        if not self._dashboard_window or not self._dashboard_window.has_active_plot():
            QMessageBox.warning(self, "Plot", "No plot is selected.")
            return
        self._dashboard_window.setup_active_plot()

    def _tile_plots(self) -> None:
        if self._dashboard_window:
            self._dashboard_window.tile_plots()

    def _cascade_plots(self) -> None:
        if self._dashboard_window:
            self._dashboard_window.cascade_plots()

    def _save_settings(self) -> None:
        self._serial_settings.to_qsettings(self._settings)
        self._appearance_settings.to_qsettings(self._settings)
        self._mqtt_settings.to_qsettings(self._settings)
        self._plot_config.to_qsettings(self._settings)
        self._variable_manager.save()
        self._settings.setValue(SK.WINDOW_GEOMETRY, self.saveGeometry())
        self._settings.setValue(SK.WINDOW_STATE, self.saveState())
        self._settings.setValue("view/tab", self._tabs.currentIndex())
        self._settings.setValue("view/splitter", self._main_splitter.saveState())
        if self._dashboard_window:
            self._dashboard_window.save_state()

    def _restore_window_state(self) -> None:
        geometry = self._settings.value(SK.WINDOW_GEOMETRY)
        if geometry:
            self.restoreGeometry(geometry)
        state = self._settings.value(SK.WINDOW_STATE)
        if state:
            self.restoreState(state)
        tab_index = self._settings.value("view/tab")
        if tab_index is not None:
            try:
                self._tabs.setCurrentIndex(int(tab_index))
            except (TypeError, ValueError):
                pass
        splitter_state = self._settings.value("view/splitter")
        if splitter_state:
            self._main_splitter.restoreState(splitter_state)
        if self._dashboard_window:
            self._dashboard_window.restore_state()


    def _store_last_preset_path(self, path: str) -> None:
        self._settings.setValue(SK.COMMANDS_LAST_PATH, path)

    def _restore_last_preset(self) -> None:
        path = self._settings.value(SK.COMMANDS_LAST_PATH, "", str)
        if path:
            try:
                self._command_toolbar.load_preset_from_path(path)
            except Exception:
                logger.warning("Failed to restore preset from %s", path, exc_info=True)
                self._settings.remove(SK.COMMANDS_LAST_PATH)
