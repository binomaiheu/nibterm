from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QIntValidator
from PySide6.QtSerialPort import QSerialPort, QSerialPortInfo
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QColorDialog,
)

from ..serial.settings import AppearanceSettings, SerialSettings


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")

        self._serial_settings = SerialSettings()
        self._appearance_settings = AppearanceSettings()

        self._tabs = QTabWidget(self)
        self._serial_tab = QWidget(self)
        self._appearance_tab = QWidget(self)
        self._tabs.addTab(self._serial_tab, "Serial")
        self._tabs.addTab(self._appearance_tab, "Appearance")

        self._build_serial_tab()
        self._build_appearance_tab()

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._apply
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(self._buttons)

    def _build_serial_tab(self) -> None:
        layout = QVBoxLayout(self._serial_tab)

        form = QFormLayout()
        self._port_combo = QComboBox(self)
        self._baud_combo = QComboBox(self)
        self._baud_combo.setEditable(True)
        self._baud_combo.lineEdit().setValidator(QIntValidator(0, 4_000_000, self))
        self._data_bits_combo = QComboBox(self)
        self._parity_combo = QComboBox(self)
        self._stop_bits_combo = QComboBox(self)
        self._flow_control_combo = QComboBox(self)
        self._line_ending_combo = QComboBox(self)

        self._local_echo = QCheckBox("Local echo")
        self._send_on_enter = QCheckBox("Send on Enter")
        self._timestamp_prefix = QCheckBox("Prefix with timestamp")
        self._auto_reconnect = QCheckBox("Auto reconnect")

        form.addRow("Port", self._port_combo)
        form.addRow("Baud rate", self._baud_combo)
        form.addRow("Data bits", self._data_bits_combo)
        form.addRow("Parity", self._parity_combo)
        form.addRow("Stop bits", self._stop_bits_combo)
        form.addRow("Flow control", self._flow_control_combo)
        form.addRow("Line ending", self._line_ending_combo)

        options_box = QGroupBox("Options")
        options_layout = QVBoxLayout(options_box)
        options_layout.addWidget(self._local_echo)
        options_layout.addWidget(self._send_on_enter)
        options_layout.addWidget(self._timestamp_prefix)
        options_layout.addWidget(self._auto_reconnect)

        layout.addLayout(form)
        layout.addWidget(options_box)
        layout.addStretch(1)

        self._populate_serial_options()

    def _build_appearance_tab(self) -> None:
        layout = QFormLayout(self._appearance_tab)

        self._font_combo = QFontComboBox(self)
        self._font_size = QSpinBox(self)
        self._font_size.setRange(6, 32)

        self._background_button = QPushButton("Choose...")
        self._text_button = QPushButton("Choose...")
        self._background_preview = QLabel()
        self._text_preview = QLabel()
        self._background_preview.setFixedWidth(60)
        self._text_preview.setFixedWidth(60)

        self._background_button.clicked.connect(
            lambda: self._choose_color("background")
        )
        self._text_button.clicked.connect(lambda: self._choose_color("text"))

        layout.addRow("Font", self._font_combo)
        layout.addRow("Font size", self._font_size)

        background_row = QWidget(self)
        background_layout = QHBoxLayout(background_row)
        background_layout.setContentsMargins(0, 0, 0, 0)
        background_layout.addWidget(self._background_button)
        background_layout.addWidget(self._background_preview)
        layout.addRow("Background", background_row)

        text_row = QWidget(self)
        text_layout = QHBoxLayout(text_row)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.addWidget(self._text_button)
        text_layout.addWidget(self._text_preview)
        layout.addRow("Text color", text_row)

    def _populate_serial_options(self) -> None:
        self._port_combo.clear()
        ports = QSerialPortInfo.availablePorts()
        if not ports:
            self._port_combo.addItem("No ports found", "")
            self._port_combo.setEnabled(False)
        else:
            self._port_combo.setEnabled(True)
            for port in ports:
                self._port_combo.addItem(port.portName(), port.portName())

        self._baud_combo.clear()
        for baud in [9600, 19200, 38400, 57600, 115200, 230400, 460800]:
            self._baud_combo.addItem(str(baud), baud)

        self._data_bits_combo.clear()
        for text, value in [
            ("5", QSerialPort.DataBits.Data5),
            ("6", QSerialPort.DataBits.Data6),
            ("7", QSerialPort.DataBits.Data7),
            ("8", QSerialPort.DataBits.Data8),
        ]:
            self._data_bits_combo.addItem(text, value)

        self._parity_combo.clear()
        for text, value in [
            ("None", QSerialPort.Parity.NoParity),
            ("Even", QSerialPort.Parity.EvenParity),
            ("Odd", QSerialPort.Parity.OddParity),
            ("Mark", QSerialPort.Parity.MarkParity),
            ("Space", QSerialPort.Parity.SpaceParity),
        ]:
            self._parity_combo.addItem(text, value)

        self._stop_bits_combo.clear()
        for text, value in [
            ("1", QSerialPort.StopBits.OneStop),
            ("1.5", QSerialPort.StopBits.OneAndHalfStop),
            ("2", QSerialPort.StopBits.TwoStop),
        ]:
            self._stop_bits_combo.addItem(text, value)

        self._flow_control_combo.clear()
        for text, value in [
            ("None", QSerialPort.FlowControl.NoFlowControl),
            ("RTS/CTS", QSerialPort.FlowControl.HardwareControl),
            ("XON/XOFF", QSerialPort.FlowControl.SoftwareControl),
        ]:
            self._flow_control_combo.addItem(text, value)

        self._line_ending_combo.clear()
        self._line_ending_combo.addItem("LF (\\n)", "\n")
        self._line_ending_combo.addItem("CR (\\r)", "\r")
        self._line_ending_combo.addItem("CRLF (\\r\\n)", "\r\n")

    def refresh_ports(self) -> None:
        self._populate_serial_options()

    def _choose_color(self, target: str) -> None:
        current = (
            self._appearance_settings.background_color
            if target == "background"
            else self._appearance_settings.text_color
        )
        color = QColorDialog.getColor(QColor(current), self)
        if not color.isValid():
            return
        if target == "background":
            self._appearance_settings.background_color = color.name()
        else:
            self._appearance_settings.text_color = color.name()
        self._update_color_previews()

    def load(self, serial_settings: SerialSettings, appearance: AppearanceSettings) -> None:
        self._serial_settings = serial_settings
        self._appearance_settings = appearance

        self._select_combo_by_data(self._port_combo, serial_settings.port_name)
        self._select_combo_by_data(self._baud_combo, serial_settings.baud_rate)
        self._select_combo_by_data(self._data_bits_combo, serial_settings.data_bits)
        self._select_combo_by_data(self._parity_combo, serial_settings.parity)
        self._select_combo_by_data(self._stop_bits_combo, serial_settings.stop_bits)
        self._select_combo_by_data(self._flow_control_combo, serial_settings.flow_control)
        self._select_combo_by_data(self._line_ending_combo, serial_settings.line_ending)

        self._local_echo.setChecked(serial_settings.local_echo)
        self._send_on_enter.setChecked(serial_settings.send_on_enter)
        self._timestamp_prefix.setChecked(serial_settings.timestamp_prefix)
        self._auto_reconnect.setChecked(serial_settings.auto_reconnect)

        self._font_combo.setCurrentFont(QFont(appearance.font_family, appearance.font_size))
        self._font_size.setValue(appearance.font_size)
        self._update_color_previews()

    def _select_combo_by_data(self, combo: QComboBox, value) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentIndex(0)

    def _update_color_previews(self) -> None:
        self._background_preview.setStyleSheet(
            f"background-color: {self._appearance_settings.background_color};"
        )
        self._text_preview.setStyleSheet(
            f"background-color: {self._appearance_settings.text_color};"
        )

    def _apply(self) -> None:
        self._serial_settings = SerialSettings(
            port_name=self._port_combo.currentData() or "",
            baud_rate=int(self._baud_combo.currentData() or self._baud_combo.currentText()),
            data_bits=self._data_bits_combo.currentData(),
            parity=self._parity_combo.currentData(),
            stop_bits=self._stop_bits_combo.currentData(),
            flow_control=self._flow_control_combo.currentData(),
            local_echo=self._local_echo.isChecked(),
            send_on_enter=self._send_on_enter.isChecked(),
            line_ending=self._line_ending_combo.currentData() or "\n",
            auto_reconnect=self._auto_reconnect.isChecked(),
            timestamp_prefix=self._timestamp_prefix.isChecked(),
        )
        self._appearance_settings = AppearanceSettings(
            font_family=self._font_combo.currentFont().family(),
            font_size=self._font_size.value(),
            background_color=self._appearance_settings.background_color,
            text_color=self._appearance_settings.text_color,
        )

    def accept(self) -> None:
        self._apply()
        super().accept()

    def serial_settings(self) -> SerialSettings:
        return self._serial_settings

    def appearance_settings(self) -> AppearanceSettings:
        return self._appearance_settings
