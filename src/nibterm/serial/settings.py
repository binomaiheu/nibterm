from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings
from PySide6.QtSerialPort import QSerialPort

from ..config import defaults
from ..config import settings_keys as SK


def _enum_value(value: int | object) -> int:
    """Extract the integer value from a Qt enum or plain int."""
    raw = getattr(value, "value", value)
    return int(raw)


@dataclass
class SerialSettings:
    port_name: str = ""
    baud_rate: int = defaults.DEFAULT_BAUD_RATE
    data_bits: QSerialPort.DataBits = defaults.DEFAULT_DATA_BITS
    parity: QSerialPort.Parity = defaults.DEFAULT_PARITY
    stop_bits: QSerialPort.StopBits = defaults.DEFAULT_STOP_BITS
    flow_control: QSerialPort.FlowControl = defaults.DEFAULT_FLOW_CONTROL
    local_echo: bool = defaults.DEFAULT_LOCAL_ECHO
    send_on_enter: bool = defaults.DEFAULT_SEND_ON_ENTER
    line_ending: str = defaults.DEFAULT_LINE_ENDING
    auto_reconnect: bool = defaults.DEFAULT_AUTO_RECONNECT
    timestamp_prefix: bool = defaults.DEFAULT_TIMESTAMP_PREFIX

    def to_qsettings(self, settings: QSettings) -> None:
        settings.setValue(SK.SERIAL_PORT_NAME, self.port_name)
        settings.setValue(SK.SERIAL_BAUD_RATE, self.baud_rate)
        settings.setValue(SK.SERIAL_DATA_BITS, _enum_value(self.data_bits))
        settings.setValue(SK.SERIAL_PARITY, _enum_value(self.parity))
        settings.setValue(SK.SERIAL_STOP_BITS, _enum_value(self.stop_bits))
        settings.setValue(SK.SERIAL_FLOW_CONTROL, _enum_value(self.flow_control))
        settings.setValue(SK.SERIAL_LOCAL_ECHO, self.local_echo)
        settings.setValue(SK.SERIAL_SEND_ON_ENTER, self.send_on_enter)
        settings.setValue(SK.SERIAL_LINE_ENDING, self.line_ending)
        settings.setValue(SK.SERIAL_AUTO_RECONNECT, self.auto_reconnect)
        settings.setValue(SK.SERIAL_TIMESTAMP_PREFIX, self.timestamp_prefix)

    @staticmethod
    def from_qsettings(settings: QSettings) -> "SerialSettings":
        return SerialSettings(
            port_name=settings.value(SK.SERIAL_PORT_NAME, "", str),
            baud_rate=settings.value(SK.SERIAL_BAUD_RATE, defaults.DEFAULT_BAUD_RATE, int),
            data_bits=QSerialPort.DataBits(
                int(settings.value(SK.SERIAL_DATA_BITS, _enum_value(defaults.DEFAULT_DATA_BITS), int))
            ),
            parity=QSerialPort.Parity(
                int(settings.value(SK.SERIAL_PARITY, _enum_value(defaults.DEFAULT_PARITY), int))
            ),
            stop_bits=QSerialPort.StopBits(
                int(settings.value(SK.SERIAL_STOP_BITS, _enum_value(defaults.DEFAULT_STOP_BITS), int))
            ),
            flow_control=QSerialPort.FlowControl(
                int(settings.value(SK.SERIAL_FLOW_CONTROL, _enum_value(defaults.DEFAULT_FLOW_CONTROL), int))
            ),
            local_echo=settings.value(SK.SERIAL_LOCAL_ECHO, defaults.DEFAULT_LOCAL_ECHO, bool),
            send_on_enter=settings.value(SK.SERIAL_SEND_ON_ENTER, defaults.DEFAULT_SEND_ON_ENTER, bool),
            line_ending=settings.value(SK.SERIAL_LINE_ENDING, defaults.DEFAULT_LINE_ENDING, str),
            auto_reconnect=settings.value(SK.SERIAL_AUTO_RECONNECT, defaults.DEFAULT_AUTO_RECONNECT, bool),
            timestamp_prefix=settings.value(SK.SERIAL_TIMESTAMP_PREFIX, defaults.DEFAULT_TIMESTAMP_PREFIX, bool),
        )


@dataclass
class AppearanceSettings:
    font_family: str = "Monospace"
    font_size: int = 11
    background_color: str = "#fff7cc"
    text_color: str = "#000000"

    def to_qsettings(self, settings: QSettings) -> None:
        settings.setValue(SK.APPEARANCE_FONT_FAMILY, self.font_family)
        settings.setValue(SK.APPEARANCE_FONT_SIZE, self.font_size)
        settings.setValue(SK.APPEARANCE_BACKGROUND_COLOR, self.background_color)
        settings.setValue(SK.APPEARANCE_TEXT_COLOR, self.text_color)

    @staticmethod
    def from_qsettings(settings: QSettings) -> "AppearanceSettings":
        return AppearanceSettings(
            font_family=settings.value(SK.APPEARANCE_FONT_FAMILY, "Monospace", str),
            font_size=settings.value(SK.APPEARANCE_FONT_SIZE, 11, int),
            background_color=settings.value(SK.APPEARANCE_BACKGROUND_COLOR, "#fff7cc", str),
            text_color=settings.value(SK.APPEARANCE_TEXT_COLOR, "#000000", str),
        )
