from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.exceptions import JsonPathParserError
from PySide6.QtCore import QPoint, QSettings, Qt, Signal, Slot
from PySide6.QtGui import QColor, QMouseEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass
class MQTTPlotVariable:
    topic: str = ""
    json_path: str = ""
    variable_name: str = ""


def _build_json_with_path_ranges(
    obj: object, path: str = "$", indent: int = 0
) -> tuple[str, list[tuple[int, int, str, str]]]:
    """Build pretty-printed JSON and a list of (start, end, json_path, key_name) for each primitive value."""
    positions: list[tuple[int, int, str, str]] = []
    chunks: list[str] = []

    def tell() -> int:
        return sum(len(c) for c in chunks)

    def _key_from_path(p: str) -> str:
        if p == "$":
            return ""
        if "." in p:
            rest = p.split(".")[-1]
        else:
            rest = p.lstrip("$.")
        # e.g. "sensors[0]" -> "sensors_0", "value" -> "value"
        rest = re.sub(r"\[\s*(\d+)\s*\]", r"_\1", rest)
        return rest or "value"

    def emit(obj: object, path: str, key_name: str) -> None:
        start = tell()
        if obj is None:
            chunks.append("null")
        elif isinstance(obj, bool):
            chunks.append("true" if obj else "false")
        elif isinstance(obj, (int, float)):
            chunks.append(json.dumps(obj))
        elif isinstance(obj, str):
            chunks.append(json.dumps(obj))
        else:
            return
        end = tell()
        positions.append((start, end, path, key_name or _key_from_path(path)))

    def walk(obj: object, path: str, indent_level: int) -> None:
        key_name = _key_from_path(path)
        if obj is None or isinstance(obj, (bool, int, float, str)):
            emit(obj, path, key_name)
            return
        if isinstance(obj, dict):
            chunks.append("{\n")
            for i, (k, v) in enumerate(obj.items()):
                sub_path = f"{path}.{k}" if path != "$" else f"$.{k}"
                chunks.append(" " * (indent_level + 2))
                chunks.append(json.dumps(k) + ": ")
                walk(v, sub_path, indent_level + 2)
                if i < len(obj) - 1:
                    chunks.append(",")
                chunks.append("\n")
            chunks.append(" " * indent_level + "}")
            return
        if isinstance(obj, list):
            chunks.append("[\n")
            for i, v in enumerate(obj):
                sub_path = f"{path}[{i}]"
                chunks.append(" " * (indent_level + 2))
                walk(v, sub_path, indent_level + 2)
                if i < len(obj) - 1:
                    chunks.append(",")
                chunks.append("\n")
            chunks.append(" " * indent_level + "]")
            return

    walk(obj, path, indent)
    return "".join(chunks), positions


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


def _sanitize_var_name(name: str) -> str:
    """Make a string safe for use as a variable/column name."""
    if not name:
        return "value"
    s = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return s.strip("_") or "value"


def _unique_variable_name(base: str, existing: set[str]) -> str:
    """Return base or base_2, base_3, ... so the result is not in existing."""
    if not base:
        base = "value"
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"


class _JsonClickableEdit(QPlainTextEdit):
    """Plain text edit that notifies on click when a JSON path can be resolved, and highlights plot variables on hover."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._path_ranges: list[tuple[int, int, str, str]] = []
        self._on_path_clicked: Callable[[str, str], None] | None = None
        self._plot_variable_paths: set[str] = set()
        self._hover_range: tuple[int, int] | None = None
        self.setMouseTracking(True)

    def set_path_ranges(self, ranges: list[tuple[int, int, str, str]]) -> None:
        self._path_ranges = ranges
        self._hover_range = None
        self._update_highlights()

    def set_plot_variable_paths(self, paths: set[str]) -> None:
        """Set json_paths that are in the plot table for the currently displayed topic."""
        self._plot_variable_paths = paths
        self._update_highlights()

    def set_on_path_clicked(self, callback: Callable[[str, str], None] | None) -> None:
        self._on_path_clicked = callback

    def _offset_at(self, pos: QPoint) -> int:
        cursor = self.cursorForPosition(pos)
        block = cursor.block()
        return block.position() + cursor.positionInBlock()

    def _range_at_offset(self, offset: int) -> tuple[int, int] | None:
        for start, end, _path, _key in self._path_ranges:
            if start <= offset < end:
                return (start, end)
        return None

    def _update_highlights(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        doc = self.document()
        for start, end, path, _key in self._path_ranges:
            in_table = path in self._plot_variable_paths
            is_hover = (start, end) == self._hover_range
            if is_hover:
                fmt = QTextCharFormat()
                fmt.setBackground(QColor("#b3d9ff"))  # light blue on hover
            elif in_table:
                fmt = QTextCharFormat()
                fmt.setBackground(QColor("#e6f3ff"))  # very light blue for "in table"
            else:
                continue
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = QTextCursor(doc)
            sel.cursor.setPosition(start)
            sel.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            selections.append(sel)
        self.setExtraSelections(selections)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if not self._path_ranges:
            return
        offset = self._offset_at(event.pos())
        new_range = self._range_at_offset(offset)
        if new_range != self._hover_range:
            self._hover_range = new_range
            self._update_highlights()

    def leaveEvent(self, event) -> None:
        super().leaveEvent(event)
        if self._hover_range is not None:
            self._hover_range = None
            self._update_highlights()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() != Qt.MouseButton.LeftButton or not self._path_ranges:
            return
        offset = self._offset_at(event.pos())
        for start, end, path, key_name in self._path_ranges:
            if start <= offset < end and self._on_path_clicked:
                self._on_path_clicked(path, key_name)
                break


class MQTTMonitorWidget(QWidget):
    plot_variables_changed = Signal(list)  # variable names in column order

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._values_callback: Callable[[dict[str, float]], None] | None = None
        self._delimiter = ","
        self._plot_variables: list[MQTTPlotVariable] = []
        self._messages_by_topic: dict[str, bytes] = {}
        self._message_time_by_topic: dict[str, float] = {}
        self._displayed_topic: str = ""
        self._settings = QSettings()

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Topic"])
        self._tree.setAlternatingRowColors(True)
        self._tree.itemSelectionChanged.connect(self._on_topic_selection_changed)

        self._message_display = _JsonClickableEdit()
        self._message_display.setReadOnly(True)
        self._message_display.setPlaceholderText(
            "MQTT messages will appear here. Click a value to add its JSON path to plot variables."
        )
        self._message_display.set_on_path_clicked(self._on_json_value_clicked)

        self._plot_table = QTableWidget(0, 3)
        self._plot_table.setHorizontalHeaderLabels(["Topic", "JSON path", "Variable name"])
        self._plot_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._plot_table.itemChanged.connect(self._on_plot_table_item_changed)
        self._plot_add = QPushButton("Add")
        self._plot_remove = QPushButton("Remove")
        self._plot_clear_all = QPushButton("Clear all")
        self._plot_add.clicked.connect(self._add_plot_var_row)
        self._plot_remove.clicked.connect(self._remove_plot_var_row)
        self._plot_clear_all.clicked.connect(self._clear_all_plot_variables)

        plot_layout = QVBoxLayout()
        plot_layout.addWidget(QLabel("Plot variables (one value per JSON path):"))
        plot_layout.addWidget(self._plot_table)
        plot_btns = QHBoxLayout()
        plot_btns.addWidget(self._plot_add)
        plot_btns.addWidget(self._plot_remove)
        plot_btns.addWidget(self._plot_clear_all)
        plot_btns.addStretch()
        plot_layout.addLayout(plot_btns)

        self._message_time_label = QLabel()
        self._message_time_label.setStyleSheet("color: gray; font-size: 0.9em;")
        right = QVBoxLayout()
        right.addWidget(
            QLabel("Message (raw / JSON). Click a value to add its path to plot variables:")
        )
        right.addWidget(self._message_time_label)
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
        self._emit_plot_variables_changed()

    def get_plot_variable_names(self) -> list[str]:
        """Variable names in column order (for syncing to Dashboard)."""
        self._sync_plot_variables_from_table()
        return [pv.variable_name for pv in self._plot_variables]

    def _emit_plot_variables_changed(self) -> None:
        self.plot_variables_changed.emit(self.get_plot_variable_names())

    def _on_plot_table_item_changed(self, _item: QTableWidgetItem) -> None:
        """Sync table to model and notify app when user edits a plot variable row."""
        self._plot_table.blockSignals(True)
        try:
            self._sync_plot_variables_from_table()
            self._emit_plot_variables_changed()
            self._update_message_display_plot_highlights()
        finally:
            self._plot_table.blockSignals(False)

    def set_values_callback(self, callback: Callable[[dict[str, float]], None] | None) -> None:
        """Called when MQTT message arrives with variable_name -> float for variables matching the message topic."""
        self._values_callback = callback

    def set_delimiter(self, delimiter: str) -> None:
        self._delimiter = delimiter or ","

    def _load_plot_variables(self) -> None:
        count = self._settings.value("mqtt/plot_var_count", 0, int)
        for i in range(count):
            topic = self._settings.value(f"mqtt/plot_var_topic_{i}", "", str)
            path = self._settings.value(f"mqtt/plot_var_path_{i}", "", str)
            name = self._settings.value(f"mqtt/plot_var_name_{i}", "", str)
            if topic or path or name:
                self._plot_variables.append(
                    MQTTPlotVariable(
                        topic=topic,
                        json_path=path,
                        variable_name=name or f"c{i}",
                    )
                )
        self._refresh_plot_table()

    def _save_plot_variables(self) -> None:
        self._settings.setValue("mqtt/plot_var_count", len(self._plot_variables))
        for i, pv in enumerate(self._plot_variables):
            self._settings.setValue(f"mqtt/plot_var_topic_{i}", pv.topic)
            self._settings.setValue(f"mqtt/plot_var_path_{i}", pv.json_path)
            self._settings.setValue(f"mqtt/plot_var_name_{i}", pv.variable_name)

    def _refresh_plot_table(self) -> None:
        """Write _plot_variables to the table. Blocks signals so programmatic updates don't trigger itemChanged."""
        self._plot_table.blockSignals(True)
        try:
            self._plot_table.setRowCount(len(self._plot_variables))
            for row, pv in enumerate(self._plot_variables):
                self._plot_table.setItem(row, 0, QTableWidgetItem(pv.topic))
                self._plot_table.setItem(row, 1, QTableWidgetItem(pv.json_path))
                self._plot_table.setItem(row, 2, QTableWidgetItem(pv.variable_name))
        finally:
            self._plot_table.blockSignals(False)

    def _sync_plot_variables_from_table(self) -> None:
        self._plot_variables.clear()
        used_names: set[str] = set()
        for row in range(self._plot_table.rowCount()):
            topic_item = self._plot_table.item(row, 0)
            path_item = self._plot_table.item(row, 1)
            name_item = self._plot_table.item(row, 2)
            topic = (topic_item.text() if topic_item else "").strip()
            path = (path_item.text() if path_item else "").strip()
            raw_name = (name_item.text() if name_item else "").strip() or f"c{row}"
            name = _unique_variable_name(raw_name, used_names)
            used_names.add(name)
            self._plot_variables.append(
                MQTTPlotVariable(topic=topic, json_path=path, variable_name=name)
            )
        self._save_plot_variables()
        self._refresh_plot_table()

    def _add_plot_var_row(self) -> None:
        self._sync_plot_variables_from_table()
        existing = {pv.variable_name for pv in self._plot_variables}
        name = _unique_variable_name("field", existing)
        self._plot_variables.append(
            MQTTPlotVariable(topic="", json_path="$.field", variable_name=name)
        )
        self._refresh_plot_table()
        self._save_plot_variables()
        self._emit_plot_variables_changed()
        self._update_message_display_plot_highlights()

    def _remove_plot_var_row(self) -> None:
        row = self._plot_table.currentRow()
        if row < 0:
            return
        self._sync_plot_variables_from_table()
        if row < len(self._plot_variables):
            self._plot_variables.pop(row)
        self._refresh_plot_table()
        self._save_plot_variables()
        self._emit_plot_variables_changed()
        self._update_message_display_plot_highlights()

    def _clear_all_plot_variables(self) -> None:
        """Remove all MQTT plot variables from the table and sync to the app."""
        self._plot_variables.clear()
        self._refresh_plot_table()
        self._save_plot_variables()
        self._emit_plot_variables_changed()
        self._update_message_display_plot_highlights()

    def _on_json_value_clicked(self, json_path: str, key_name: str) -> None:
        """Add the clicked JSON path to plot variables (avoid duplicates)."""
        self._sync_plot_variables_from_table()
        topic = self._displayed_topic
        if any(
            pv.topic == topic and pv.json_path == json_path
            for pv in self._plot_variables
        ):
            return
        base = _sanitize_var_name(key_name)
        existing = {pv.variable_name for pv in self._plot_variables}
        name = _unique_variable_name(base, existing)
        self._plot_variables.append(
            MQTTPlotVariable(topic=topic, json_path=json_path, variable_name=name)
        )
        self._refresh_plot_table()
        self._save_plot_variables()
        self._emit_plot_variables_changed()
        self._update_message_display_plot_highlights()

    def _find_or_create_path(
        self, parent: QTreeWidgetItem, topic: str
    ) -> QTreeWidgetItem:
        parts = [p for p in topic.split("/") if p]
        current = parent
        for i, part in enumerate(parts):
            path_so_far = "/".join(parts[: i + 1])
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
            current.setData(0, Qt.ItemDataRole.UserRole, path_so_far)
        return current

    def _ensure_topic_in_tree_fixed(self, topic: str) -> None:
        parts = [p for p in topic.split("/") if p]
        if not parts:
            return
        root = self._tree.invisibleRootItem()
        self._find_or_create_path(root, topic)

    def _on_topic_selection_changed(self) -> None:
        items = self._tree.selectedItems()
        if not items:
            return
        item = items[0]
        topic = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(topic, str) and topic:
            self._show_message_for_topic(topic)

    def _show_message_for_topic(self, topic: str) -> None:
        self._displayed_topic = topic
        self._update_message_time_label(topic)
        payload = self._messages_by_topic.get(topic)
        if payload is None:
            self._message_display.setPlainText("")
            self._message_display.set_path_ranges([])
            return
        try:
            text = payload.decode("utf-8", errors="replace")
        except Exception:
            text = str(payload)
        try:
            obj = json.loads(text)
            display, path_ranges = _build_json_with_path_ranges(obj)
            self._message_display.setPlainText(display)
            self._message_display.set_path_ranges(path_ranges)
        except Exception:
            self._message_display.setPlainText(text)
            self._message_display.set_path_ranges([])
        self._update_message_display_plot_highlights()

    def _update_message_time_label(self, topic: str) -> None:
        """Show the time the selected topic's last message was received."""
        ts = self._message_time_by_topic.get(topic)
        if ts is None:
            self._message_time_label.setText("Received: —")
            return
        dt = datetime.fromtimestamp(ts)
        self._message_time_label.setText(f"Received: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

    def _update_message_display_plot_highlights(self) -> None:
        """Tell the message display which json_paths are in the plot table for the displayed topic."""
        paths = {
            pv.json_path
            for pv in self._plot_variables
            if pv.topic == self._displayed_topic and pv.json_path
        }
        self._message_display.set_plot_variable_paths(paths)

    @Slot(str, bytes)
    def on_message_received(self, topic: str, payload: bytes) -> None:
        self._messages_by_topic[topic] = payload
        self._message_time_by_topic[topic] = time.time()
        self._ensure_topic_in_tree_fixed(topic)

        if self._displayed_topic == topic or not self._displayed_topic:
            self._displayed_topic = topic
            self._update_message_time_label(topic)
            try:
                text = payload.decode("utf-8", errors="replace")
            except Exception:
                text = str(payload)
            try:
                obj = json.loads(text)
                display, path_ranges = _build_json_with_path_ranges(obj)
                self._message_display.setPlainText(display)
                self._message_display.set_path_ranges(path_ranges)
            except Exception:
                self._message_display.setPlainText(text)
                self._message_display.set_path_ranges([])
            self._update_message_display_plot_highlights()

        if not self._values_callback:
            return
        self._sync_plot_variables_from_table()
        if not self._plot_variables:
            return
        try:
            text = payload.decode("utf-8", errors="replace")
            obj = json.loads(text)
        except Exception:
            return
        values_by_name: dict[str, float] = {}
        for pv in self._plot_variables:
            if pv.topic != topic:
                continue
            v = _extract_json_value(obj, pv.json_path)
            if v is not None:
                values_by_name[pv.variable_name] = v
        if values_by_name:
            self._values_callback(values_by_name)
