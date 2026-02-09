from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtSerialPort import QSerialPort

from ..config import defaults


def _enum_value(value) -> int:
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
        settings.setValue("serial/port_name", self.port_name)
        settings.setValue("serial/baud_rate", self.baud_rate)
        settings.setValue("serial/data_bits", _enum_value(self.data_bits))
        settings.setValue("serial/parity", _enum_value(self.parity))
        settings.setValue("serial/stop_bits", _enum_value(self.stop_bits))
        settings.setValue("serial/flow_control", _enum_value(self.flow_control))
        settings.setValue("serial/local_echo", self.local_echo)
        settings.setValue("serial/send_on_enter", self.send_on_enter)
        settings.setValue("serial/line_ending", self.line_ending)
        settings.setValue("serial/auto_reconnect", self.auto_reconnect)
        settings.setValue("serial/timestamp_prefix", self.timestamp_prefix)

    @staticmethod
    def from_qsettings(settings: QSettings) -> "SerialSettings":
        return SerialSettings(
            port_name=settings.value("serial/port_name", "", str),
            baud_rate=settings.value(
                "serial/baud_rate",
                defaults.DEFAULT_BAUD_RATE,
                int,
            ),
            data_bits=QSerialPort.DataBits(
                int(
                    settings.value(
                        "serial/data_bits",
                        _enum_value(defaults.DEFAULT_DATA_BITS),
                        int,
                    )
                )
            ),
            parity=QSerialPort.Parity(
                int(
                    settings.value(
                        "serial/parity",
                        _enum_value(defaults.DEFAULT_PARITY),
                        int,
                    )
                )
            ),
            stop_bits=QSerialPort.StopBits(
                int(
                    settings.value(
                        "serial/stop_bits",
                        _enum_value(defaults.DEFAULT_STOP_BITS),
                        int,
                    )
                )
            ),
            flow_control=QSerialPort.FlowControl(
                int(
                    settings.value(
                        "serial/flow_control",
                        _enum_value(defaults.DEFAULT_FLOW_CONTROL),
                        int,
                    )
                )
            ),
            local_echo=settings.value(
                "serial/local_echo",
                defaults.DEFAULT_LOCAL_ECHO,
                bool,
            ),
            send_on_enter=settings.value(
                "serial/send_on_enter",
                defaults.DEFAULT_SEND_ON_ENTER,
                bool,
            ),
            line_ending=settings.value(
                "serial/line_ending",
                defaults.DEFAULT_LINE_ENDING,
                str,
            ),
            auto_reconnect=settings.value(
                "serial/auto_reconnect",
                defaults.DEFAULT_AUTO_RECONNECT,
                bool,
            ),
            timestamp_prefix=settings.value(
                "serial/timestamp_prefix",
                defaults.DEFAULT_TIMESTAMP_PREFIX,
                bool,
            ),
        )


@dataclass
class AppearanceSettings:
    font_family: str = "Monospace"
    font_size: int = 11
    background_color: str = "#fff7cc"
    text_color: str = "#000000"

    def to_qsettings(self, settings: QSettings) -> None:
        settings.setValue("appearance/font_family", self.font_family)
        settings.setValue("appearance/font_size", self.font_size)
        settings.setValue("appearance/background_color", self.background_color)
        settings.setValue("appearance/text_color", self.text_color)

    @staticmethod
    def from_qsettings(settings: QSettings) -> "AppearanceSettings":
        return AppearanceSettings(
            font_family=settings.value(
                "appearance/font_family",
                "Monospace",
                str,
            ),
            font_size=settings.value("appearance/font_size", 11, int),
            background_color=settings.value(
                "appearance/background_color",
                "#fff7cc",
                str,
            ),
            text_color=settings.value(
                "appearance/text_color",
                "#000000",
                str,
            ),
        )
