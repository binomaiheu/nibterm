from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFont, QHideEvent, QShowEvent
from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class DevicesWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._known_ports: frozenset[str] = frozenset()
        self._build_ui()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(500)
        self._poll_timer.timeout.connect(self._poll)
        self._do_poll(log_changes=False)

    def _build_ui(self) -> None:
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Port", "Location", "Description", "Manufacturer", "Serial #", "VID:PID"]
        )
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Monospace", 9))
        self._log.setMaximumBlockCount(1000)
        self._log.setPlaceholderText(
            "Device connect/disconnect events will appear here."
        )

        log_box = QGroupBox("Device log")
        log_layout = QVBoxLayout(log_box)
        log_layout.addWidget(self._log)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._table)
        splitter.addWidget(log_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Connected serial devices:"))
        layout.addWidget(splitter)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._do_poll(log_changes=True)
        self._poll_timer.start()

    def hideEvent(self, event: QHideEvent) -> None:
        self._poll_timer.stop()
        super().hideEvent(event)

    @Slot()
    def _poll(self) -> None:
        self._do_poll(log_changes=True)

    def _do_poll(self, log_changes: bool = True) -> None:
        ports = QSerialPortInfo.availablePorts()
        ports_by_name = {p.portName(): p for p in ports}
        new_names = frozenset(ports_by_name.keys())

        added = new_names - self._known_ports
        removed = self._known_ports - new_names

        if added or removed or not self._known_ports and not new_names:
            self._rebuild_table(ports)
            if log_changes and (added or removed):
                self._log_changes(added, removed, ports_by_name)
            self._known_ports = new_names

    def _rebuild_table(self, ports: list[QSerialPortInfo]) -> None:
        sorted_ports = sorted(ports, key=lambda p: p.portName())
        self._table.setRowCount(len(sorted_ports))
        for row, info in enumerate(sorted_ports):
            self._set_cell(row, 0, info.portName())
            self._set_cell(row, 1, info.systemLocation())
            self._set_cell(row, 2, info.description())
            self._set_cell(row, 3, info.manufacturer())
            self._set_cell(row, 4, info.serialNumber())
            self._set_cell(row, 5, self._format_vid_pid(info))

    def _set_cell(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._table.setItem(row, col, item)

    def _log_changes(
        self,
        added: frozenset[str],
        removed: frozenset[str],
        ports_by_name: dict[str, QSerialPortInfo],
    ) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        for name in sorted(removed):
            self._log.appendPlainText(f"[{ts}] - {name}")
        for name in sorted(added):
            info = ports_by_name[name]
            desc = info.description()
            vid_pid = self._format_vid_pid(info)
            parts = [f"[{ts}] + {name}"]
            if desc:
                parts.append(f"  {desc}")
            if vid_pid:
                parts.append(f"  ({vid_pid})")
            self._log.appendPlainText("".join(parts))

    def _format_vid_pid(self, info: QSerialPortInfo) -> str:
        has_vid = info.hasVendorIdentifier()
        has_pid = info.hasProductIdentifier()
        if has_vid or has_pid:
            vid = f"{info.vendorIdentifier():04X}" if has_vid else "????"
            pid = f"{info.productIdentifier():04X}" if has_pid else "????"
            return f"{vid}:{pid}"
        return ""
