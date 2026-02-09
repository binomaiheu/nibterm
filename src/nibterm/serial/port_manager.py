from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtSerialPort import QSerialPort

from .settings import SerialSettings


class PortManager(QObject):
    data_received = Signal(bytes)
    connection_changed = Signal(bool)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._serial = QSerialPort(self)
        self._serial.readyRead.connect(self._read_ready)
        self._serial.errorOccurred.connect(self._handle_error)

        self._auto_reconnect = False
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(3000)
        self._reconnect_timer.timeout.connect(self._try_reconnect)
        self._last_settings: SerialSettings | None = None

    def is_open(self) -> bool:
        return self._serial.isOpen()

    def set_auto_reconnect(self, enabled: bool) -> None:
        self._auto_reconnect = enabled
        if not enabled:
            self._reconnect_timer.stop()

    def open(self, settings: SerialSettings) -> bool:
        self._last_settings = settings
        self._serial.setPortName(settings.port_name)
        self._serial.setBaudRate(settings.baud_rate)
        self._serial.setDataBits(settings.data_bits)
        self._serial.setParity(settings.parity)
        self._serial.setStopBits(settings.stop_bits)
        self._serial.setFlowControl(settings.flow_control)

        if self._serial.open(QSerialPort.OpenModeFlag.ReadWrite):
            self._reconnect_timer.stop()
            self.connection_changed.emit(True)
            return True

        self.error.emit(self._serial.errorString())
        return False

    def close(self) -> None:
        if self._serial.isOpen():
            self._serial.close()
        self.connection_changed.emit(False)

    def write(self, data: bytes) -> None:
        if not data:
            return
        if self._serial.isOpen():
            self._serial.write(data)

    @Slot()
    def _read_ready(self) -> None:
        data = self._serial.readAll()
        if not data.isEmpty():
            self.data_received.emit(bytes(data))

    @Slot(QSerialPort.SerialPortError)
    def _handle_error(self, error: QSerialPort.SerialPortError) -> None:
        if error == QSerialPort.SerialPortError.NoError:
            return
        self.error.emit(self._serial.errorString())
        if error == QSerialPort.SerialPortError.ResourceError:
            self.close()
            if self._auto_reconnect:
                self._reconnect_timer.start()

    @Slot()
    def _try_reconnect(self) -> None:
        if self._last_settings is None or self._serial.isOpen():
            self._reconnect_timer.stop()
            return
        if self.open(self._last_settings):
            self._reconnect_timer.stop()
