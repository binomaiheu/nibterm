from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.exceptions import JsonPathParserError
from PySide6.QtCore import QSettings, Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass
class MQTTPlotVariable:
    json_path: str = ""
    variable_name: str = ""


def _extract_json_value(data: object, path_str: str) -> float | None:
    try:
        path = jsonpath_parse(path_str)
        matches = path.find(data)
        if not matches:
            return None
        val = matches[0].value
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                return None
        return None
    except (JsonPathParserError, Exception):
        return None


class MQTTMonitorWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._line_callback: Callable[[str], None] | None = None
        self._delimiter = ","
        self._plot_variables: list[MQTTPlotVariable] = []
        self._last_topic: str = ""
        self._last_payload: bytes = b""
        self._settings = QSettings()

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Topic"])
        self._tree.setAlternatingRowColors(True)

        self._message_display = QPlainTextEdit()
        self._message_display.setReadOnly(True)
        self._message_display.setPlaceholderText("MQTT messages will appear here…")

        self._plot_table = QTableWidget(0, 2)
        self._plot_table.setHorizontalHeaderLabels(["JSON path", "Variable name"])
        self._plot_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._plot_add = QPushButton("Add")
        self._plot_remove = QPushButton("Remove")
        self._plot_add.clicked.connect(self._add_plot_var_row)
        self._plot_remove.clicked.connect(self._remove_plot_var_row)

        plot_layout = QVBoxLayout()
        plot_layout.addWidget(QLabel("Plot variables (one value per JSON path):"))
        plot_layout.addWidget(self._plot_table)
        plot_btns = QHBoxLayout()
        plot_btns.addWidget(self._plot_add)
        plot_btns.addWidget(self._plot_remove)
        plot_btns.addStretch()
        plot_layout.addLayout(plot_btns)

        right = QVBoxLayout()
        right.addWidget(QLabel("Message (raw / JSON):"))
        right.addWidget(self._message_display)
        right.addLayout(plot_layout)
        right_widget = QWidget()
        right_widget.setLayout(right)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._tree)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self._load_plot_variables()

    def set_line_callback(self, callback: Callable[[str], None] | None) -> None:
        self._line_callback = callback

    def set_delimiter(self, delimiter: str) -> None:
        self._delimiter = delimiter or ","

    def _load_plot_variables(self) -> None:
        count = self._settings.value("mqtt/plot_var_count", 0, int)
        for i in range(count):
            path = self._settings.value(f"mqtt/plot_var_path_{i}", "", str)
            name = self._settings.value(f"mqtt/plot_var_name_{i}", "", str)
            if path or name:
                self._plot_variables.append(
                    MQTTPlotVariable(json_path=path, variable_name=name or f"c{i}")
                )
        self._refresh_plot_table()

    def _save_plot_variables(self) -> None:
        self._settings.setValue("mqtt/plot_var_count", len(self._plot_variables))
        for i, pv in enumerate(self._plot_variables):
            self._settings.setValue(f"mqtt/plot_var_path_{i}", pv.json_path)
            self._settings.setValue(f"mqtt/plot_var_name_{i}", pv.variable_name)

    def _refresh_plot_table(self) -> None:
        self._plot_table.setRowCount(len(self._plot_variables))
        for row, pv in enumerate(self._plot_variables):
            self._plot_table.setItem(row, 0, QTableWidgetItem(pv.json_path))
            self._plot_table.setItem(row, 1, QTableWidgetItem(pv.variable_name))

    def _sync_plot_variables_from_table(self) -> None:
        self._plot_variables.clear()
        for row in range(self._plot_table.rowCount()):
            path_item = self._plot_table.item(row, 0)
            name_item = self._plot_table.item(row, 1)
            path = (path_item.text() if path_item else "").strip()
            name = (name_item.text() if name_item else "").strip() or f"c{row}"
            self._plot_variables.append(
                MQTTPlotVariable(json_path=path, variable_name=name)
            )
        self._save_plot_variables()

    def _add_plot_var_row(self) -> None:
        self._sync_plot_variables_from_table()
        self._plot_variables.append(MQTTPlotVariable("$.field", "field"))
        self._refresh_plot_table()
        self._save_plot_variables()

    def _remove_plot_var_row(self) -> None:
        row = self._plot_table.currentRow()
        if row < 0:
            return
        self._sync_plot_variables_from_table()
        if row < len(self._plot_variables):
            self._plot_variables.pop(row)
        self._refresh_plot_table()
        self._save_plot_variables()

    def _find_or_create_path(self, parent: QTreeWidgetItem, path: str) -> QTreeWidgetItem:
        parts = [p for p in path.split("/") if p]
        current = parent
        for part in parts:
            found = None
            for c in range(current.childCount()):
                if current.child(c).text(0) == part:
                    found = current.child(c)
                    break
            if found is not None:
                current = found
            else:
                child = QTreeWidgetItem([part])
                current.addChild(child)
                current = child
        return current

    def _ensure_topic_in_tree_fixed(self, topic: str) -> None:
        parts = [p for p in topic.split("/") if p]
        if not parts:
            return
        root = self._tree.invisibleRootItem()
        self._find_or_create_path(root, topic)

    @Slot(str, bytes)
    def on_message_received(self, topic: str, payload: bytes) -> None:
        self._last_topic = topic
        self._last_payload = payload
        self._ensure_topic_in_tree_fixed(topic)

        try:
            text = payload.decode("utf-8", errors="replace")
        except Exception:
            text = str(payload)
        try:
            obj = json.loads(text)
            display = json.dumps(obj, indent=2)
        except Exception:
            display = text
        self._message_display.setPlainText(display)

        if not self._line_callback:
            return
        self._sync_plot_variables_from_table()
        if not self._plot_variables:
            return
        try:
            obj = json.loads(text)
        except Exception:
            return
        values: list[str] = []
        for pv in self._plot_variables:
            v = _extract_json_value(obj, pv.json_path)
            if v is None:
                values.append("")
            else:
                values.append(str(v))
        line = self._delimiter.join(values)
        self._line_callback(line)
