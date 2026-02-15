from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Callable

logger = logging.getLogger(__name__)

from PySide6.QtCore import QEvent, QPoint, Qt, Signal, Slot
from PySide6.QtGui import QColor, QMouseEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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

from ..config.variable import TopicParserConfig, VariableDefinition
from ..data.json_utils import (
    build_json_with_path_ranges,
    extract_json_value,
    sanitize_var_name,
    unique_variable_name,
)
from ..data.parsers import parse_csv_line, parse_json_payload, parse_regex_value
from .clickable_display import PathClickableEdit, build_csv_column_ranges

# Forward reference -- set at runtime by MainWindow
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..data.variable_manager import VariableManager


class MQTTMonitorWidget(QWidget):
    """MQTT topic browser and quick-add variable table.

    The table is now a *filtered view* of the MQTT variables in
    ``VariableManager``.  Adding or editing here updates the manager
    directly.
    """

    def __init__(self, variable_manager: "VariableManager", parent=None) -> None:
        super().__init__(parent)
        self._variable_manager = variable_manager
        self._values_callback: Callable[[dict[str, float]], None] | None = None
        self._messages_by_topic: dict[str, bytes] = {}
        self._message_time_by_topic: dict[str, float] = {}
        self._displayed_topic: str = ""
        self._displayed_topic_for_parser: str = ""

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Topic"])
        self._tree.setAlternatingRowColors(True)
        self._tree.itemSelectionChanged.connect(self._on_topic_selection_changed)

        # Per-topic parser config (shown when a topic is selected)
        self._parser_panel = QWidget()
        parser_layout = QHBoxLayout(self._parser_panel)
        parser_layout.setContentsMargins(0, 4, 0, 4)
        parser_layout.addWidget(QLabel("Parse this topic as:"))
        self._topic_parser_mode_combo = QComboBox()
        self._topic_parser_mode_combo.addItem("JSON", "json")
        self._topic_parser_mode_combo.addItem("CSV", "csv")
        self._topic_parser_mode_combo.currentIndexChanged.connect(
            self._on_topic_parser_mode_changed
        )
        parser_layout.addWidget(self._topic_parser_mode_combo)
        self._topic_parser_delimiter_label = QLabel("Delimiter:")
        self._topic_parser_delimiter_edit = QLineEdit(",")
        self._topic_parser_delimiter_edit.setMaxLength(4)
        self._topic_parser_delimiter_edit.editingFinished.connect(
            self._on_topic_parser_delimiter_changed
        )
        parser_layout.addWidget(self._topic_parser_delimiter_label)
        parser_layout.addWidget(self._topic_parser_delimiter_edit)
        parser_layout.addStretch()
        self._parser_panel.setVisible(False)

        self._message_display = PathClickableEdit()
        self._message_display.setReadOnly(True)
        self._message_display.setPlaceholderText(
            "MQTT messages will appear here. Click a value to add its JSON path to plot variables."
        )
        self._message_display.set_on_path_clicked(self._on_value_clicked)

        self._plot_table = QTableWidget(0, 3)
        self._plot_table.setHorizontalHeaderLabels(["Topic", "Extraction", "Variable name"])
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
        plot_layout.addWidget(
            QLabel("Plot variables (click a JSON value or CSV column to add):")
        )
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
        right.addWidget(self._parser_panel)
        right.addWidget(
            QLabel("Message (raw). Click a JSON value or CSV column to add it as a plot variable.")
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

        # Populate table from manager
        self._refresh_table_from_manager()

        # Listen for external changes (e.g. Variables dialog)
        self._variable_manager.variables_changed.connect(self._refresh_table_from_manager)

    def refresh_from_manager(self) -> None:
        """Public method -- called by MainWindow after Variables dialog changes."""
        self._refresh_table_from_manager()

    def set_values_callback(self, callback: Callable[[dict[str, float]], None] | None) -> None:
        """Called when MQTT message arrives with variable_name -> float for variables matching the message topic."""
        self._values_callback = callback

    # -- table <-> manager sync -----------------------------------------------

    def _extraction_display(self, v: VariableDefinition) -> str:
        """Format extraction for table based on topic's parser."""
        cfg = self._variable_manager.get_topic_parser_config(v.mqtt_topic)
        if cfg.mode == "csv":
            return f"column {v.csv_column}"
        if cfg.mode == "json":
            return v.json_path or ""
        if cfg.mode == "regex":
            if v.regex_pattern:
                return f"{v.regex_pattern} (group {v.regex_group})"
            return "(regex — not yet configured)"
        return ""

    def _refresh_table_from_manager(self) -> None:
        """Populate the MQTT quick-add table from the VariableManager's MQTT variables."""
        self._plot_table.blockSignals(True)
        try:
            mqtt_vars = self._variable_manager.get_mqtt_variables()
            self._plot_table.setRowCount(len(mqtt_vars))
            for row, v in enumerate(mqtt_vars):
                self._plot_table.setItem(row, 0, QTableWidgetItem(v.mqtt_topic))
                self._plot_table.setItem(row, 1, QTableWidgetItem(self._extraction_display(v)))
                self._plot_table.setItem(row, 2, QTableWidgetItem(v.name))
        finally:
            self._plot_table.blockSignals(False)
        self._update_message_display_plot_highlights()

    def _parse_extraction_for_topic(self, topic: str, extraction: str) -> VariableDefinition:
        """Build variable with extraction fields set from table text (by topic parser)."""
        cfg = self._variable_manager.get_topic_parser_config(topic)
        extraction = extraction.strip()
        if cfg.mode == "csv":
            col = 0
            if extraction.startswith("column "):
                try:
                    col = int(extraction[7:].strip())
                except ValueError:
                    pass
            else:
                try:
                    col = int(extraction)
                except ValueError:
                    pass
            return VariableDefinition(
                name="",
                source="mqtt",
                mqtt_topic=topic,
                csv_column=col,
            )
        if cfg.mode == "regex":
            # Keep regex placeholder; editing not supported from table yet
            return VariableDefinition(
                name="",
                source="mqtt",
                mqtt_topic=topic,
                regex_pattern="",
                regex_group=1,
            )
        # JSON (default)
        return VariableDefinition(
            name="",
            source="mqtt",
            mqtt_topic=topic,
            json_path=extraction or "$",
        )

    def _sync_table_to_manager(self) -> None:
        """Read the table rows and update the VariableManager's MQTT variables accordingly."""
        current_mqtt = self._variable_manager.get_mqtt_variables()
        new_mqtt_vars: list[VariableDefinition] = []
        for row in range(self._plot_table.rowCount()):
            topic_item = self._plot_table.item(row, 0)
            extraction_item = self._plot_table.item(row, 1)
            name_item = self._plot_table.item(row, 2)
            topic = (topic_item.text() if topic_item else "").strip()
            extraction = (extraction_item.text() if extraction_item else "").strip()
            name = (name_item.text() if name_item else "").strip()
            if not name:
                name = f"mqtt_{row}"
            var = self._parse_extraction_for_topic(topic, extraction)
            var.name = name
            # Preserve regex pattern/group when topic is regex (editing not supported yet)
            if row < len(current_mqtt) and var.mqtt_topic:
                cfg = self._variable_manager.get_topic_parser_config(var.mqtt_topic)
                if cfg.mode == "regex" and current_mqtt[row].regex_pattern:
                    var.regex_pattern = current_mqtt[row].regex_pattern
                    var.regex_group = current_mqtt[row].regex_group
            new_mqtt_vars.append(var)

        # Build the full variable list: non-MQTT variables stay unchanged
        non_mqtt = [v for v in self._variable_manager.variables if v.source != "mqtt"]

        # Ensure unique names across all variables
        used_names: set[str] = {v.name for v in non_mqtt}
        for v in new_mqtt_vars:
            v.name = unique_variable_name(v.name, used_names)
            used_names.add(v.name)

        all_vars = non_mqtt + new_mqtt_vars
        # Block the signal to avoid re-entry
        self._variable_manager.variables_changed.disconnect(self._refresh_table_from_manager)
        try:
            self._variable_manager.set_variables(all_vars)
        finally:
            self._variable_manager.variables_changed.connect(self._refresh_table_from_manager)

        # Refresh table to reflect name deduplication etc.
        self._refresh_table_from_manager()

    def _on_plot_table_item_changed(self, _item: QTableWidgetItem) -> None:
        """Sync table to manager when user edits a cell."""
        self._plot_table.blockSignals(True)
        try:
            self._sync_table_to_manager()
            self._update_message_display_plot_highlights()
        finally:
            self._plot_table.blockSignals(False)

    def _add_plot_var_row(self) -> None:
        existing = {v.name for v in self._variable_manager.variables}
        topic = self._displayed_topic_for_parser or ""
        cfg = self._variable_manager.get_topic_parser_config(topic) if topic else None
        if cfg and cfg.mode == "csv":
            name = unique_variable_name("col0", existing)
            self._variable_manager.add_variable(
                VariableDefinition(
                    name=name,
                    source="mqtt",
                    mqtt_topic=topic,
                    csv_column=0,
                )
            )
        elif cfg and cfg.mode == "regex":
            name = unique_variable_name("regex_var", existing)
            self._variable_manager.add_variable(
                VariableDefinition(
                    name=name,
                    source="mqtt",
                    mqtt_topic=topic,
                    regex_pattern="",
                    regex_group=1,
                )
            )
        else:
            name = unique_variable_name("field", existing)
            self._variable_manager.add_variable(
                VariableDefinition(
                    name=name,
                    source="mqtt",
                    mqtt_topic=topic,
                    json_path="$.field",
                )
            )
        self._update_message_display_plot_highlights()

    def _remove_plot_var_row(self) -> None:
        row = self._plot_table.currentRow()
        if row < 0:
            return
        mqtt_vars = self._variable_manager.get_mqtt_variables()
        if row < len(mqtt_vars):
            self._variable_manager.remove_variable(mqtt_vars[row].name)
        self._update_message_display_plot_highlights()

    def _clear_all_plot_variables(self) -> None:
        """Remove all MQTT plot variables."""
        self._variable_manager.remove_all_mqtt_variables()
        self._update_message_display_plot_highlights()

    def _on_value_clicked(self, path: str, key_name: str) -> None:
        """Add the clicked JSON path or CSV column to plot variables (avoid duplicates)."""
        topic = self._displayed_topic
        mqtt_vars = self._variable_manager.get_mqtt_variables()
        if path.startswith("__column_"):
            try:
                col = int(path.replace("__column_", ""))
            except ValueError:
                return
            if any(v.mqtt_topic == topic and v.csv_column == col for v in mqtt_vars):
                return
            existing = {v.name for v in self._variable_manager.variables}
            name = unique_variable_name(f"col{col}", existing)
            self._variable_manager.add_variable(
                VariableDefinition(
                    name=name,
                    source="mqtt",
                    mqtt_topic=topic,
                    csv_column=col,
                )
            )
        else:
            if any(v.mqtt_topic == topic and v.json_path == path for v in mqtt_vars):
                return
            base = sanitize_var_name(key_name)
            existing = {v.name for v in self._variable_manager.variables}
            name = unique_variable_name(base, existing)
            self._variable_manager.add_variable(
                VariableDefinition(
                    name=name,
                    source="mqtt",
                    mqtt_topic=topic,
                    json_path=path,
                )
            )
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
            self._parser_panel.setVisible(False)
            return
        item = items[0]
        topic = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(topic, str) and topic:
            self._displayed_topic_for_parser = topic
            cfg = self._variable_manager.get_topic_parser_config(topic)
            self._topic_parser_mode_combo.blockSignals(True)
            idx = self._topic_parser_mode_combo.findData(cfg.mode)
            if idx >= 0:
                self._topic_parser_mode_combo.setCurrentIndex(idx)
            self._topic_parser_delimiter_edit.setText(cfg.csv_delimiter)
            self._topic_parser_mode_combo.blockSignals(False)
            self._update_topic_parser_delimiter_visibility()
            self._parser_panel.setVisible(True)
            self._show_message_for_topic(topic)
        else:
            self._parser_panel.setVisible(False)

    def _on_topic_parser_mode_changed(self) -> None:
        if self._displayed_topic_for_parser:
            cfg = TopicParserConfig(
                mode=self._topic_parser_mode_combo.currentData(),
                csv_delimiter=self._topic_parser_delimiter_edit.text().strip() or ",",
            )
            self._variable_manager.set_topic_parser_config(
                self._displayed_topic_for_parser, cfg
            )
        self._update_topic_parser_delimiter_visibility()

    def _update_topic_parser_delimiter_visibility(self) -> None:
        is_csv = self._topic_parser_mode_combo.currentData() == "csv"
        self._topic_parser_delimiter_label.setVisible(is_csv)
        self._topic_parser_delimiter_edit.setVisible(is_csv)

    def _on_topic_parser_delimiter_changed(self) -> None:
        if not self._displayed_topic_for_parser:
            return
        cfg = self._variable_manager.get_topic_parser_config(
            self._displayed_topic_for_parser
        )
        cfg = TopicParserConfig(
            mode=cfg.mode,
            csv_delimiter=self._topic_parser_delimiter_edit.text().strip() or ",",
        )
        self._variable_manager.set_topic_parser_config(
            self._displayed_topic_for_parser, cfg
        )
        # Refresh message display so CSV column ranges use new delimiter
        self._show_message_for_topic(self._displayed_topic_for_parser)

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
        except (UnicodeDecodeError, AttributeError):
            text = str(payload)
        cfg = self._variable_manager.get_topic_parser_config(topic)
        if cfg.mode == "json":
            try:
                obj = json.loads(text)
                display, path_ranges = build_json_with_path_ranges(obj)
                self._message_display.setPlainText(display)
                self._message_display.set_path_ranges(path_ranges)
            except (json.JSONDecodeError, TypeError, ValueError):
                self._message_display.setPlainText(text)
                self._message_display.set_path_ranges([])
        else:
            if cfg.mode == "csv":
                path_ranges = build_csv_column_ranges(text, cfg.csv_delimiter or ",")
                self._message_display.setPlainText(text)
                self._message_display.set_path_ranges(path_ranges)
            else:
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
        """Tell the message display which paths/columns are in the plot table for the displayed topic."""
        mqtt_vars = self._variable_manager.get_mqtt_variables()
        cfg = (
            self._variable_manager.get_topic_parser_config(self._displayed_topic)
            if self._displayed_topic
            else None
        )
        paths: set[str] = set()
        for v in mqtt_vars:
            if v.mqtt_topic != self._displayed_topic:
                continue
            if cfg and cfg.mode == "csv":
                paths.add(f"__column_{v.csv_column}")
            else:
                if v.json_path:
                    paths.add(v.json_path)
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
            except (UnicodeDecodeError, AttributeError):
                text = str(payload)
            cfg = self._variable_manager.get_topic_parser_config(topic)
            if cfg.mode == "json":
                try:
                    obj = json.loads(text)
                    display, path_ranges = build_json_with_path_ranges(obj)
                    self._message_display.setPlainText(display)
                    self._message_display.set_path_ranges(path_ranges)
                except (json.JSONDecodeError, TypeError, ValueError):
                    self._message_display.setPlainText(text)
                    self._message_display.set_path_ranges([])
            else:
                if cfg.mode == "csv":
                    path_ranges = build_csv_column_ranges(text, cfg.csv_delimiter or ",")
                    self._message_display.setPlainText(text)
                    self._message_display.set_path_ranges(path_ranges)
                else:
                    self._message_display.setPlainText(text)
                    self._message_display.set_path_ranges([])
            self._update_message_display_plot_highlights()

        if not self._values_callback:
            return
        mqtt_vars = self._variable_manager.get_mqtt_variables()
        if not mqtt_vars:
            return
        try:
            text = payload.decode("utf-8", errors="replace")
        except (UnicodeDecodeError, TypeError, ValueError):
            return
        cfg = self._variable_manager.get_topic_parser_config(topic)
        values_by_name = self._extract_mqtt_values_for_topic(topic, text, cfg, mqtt_vars)
        if values_by_name:
            self._values_callback(values_by_name)

    def _extract_mqtt_values_for_topic(
        self,
        topic: str,
        text: str,
        cfg: TopicParserConfig,
        mqtt_vars: list[VariableDefinition],
    ) -> dict[str, float]:
        """Build name -> float for variables with mqtt_topic == topic using shared parsers."""
        values_by_name: dict[str, float] = {}
        for v in mqtt_vars:
            if v.mqtt_topic != topic:
                continue
            if cfg.mode == "csv":
                column_values = parse_csv_line(text, cfg.csv_delimiter, column_indices=None)
                if v.csv_column in column_values:
                    values_by_name[v.name] = column_values[v.csv_column]
            elif cfg.mode == "json":
                obj = parse_json_payload(text)
                if obj is not None and v.json_path:
                    val = extract_json_value(obj, v.json_path)
                    if val is not None:
                        try:
                            values_by_name[v.name] = float(val)
                        except (TypeError, ValueError):
                            pass
            elif cfg.mode == "regex":
                if v.regex_pattern:
                    val = parse_regex_value(text, v.regex_pattern, v.regex_group)
                    if val is not None:
                        values_by_name[v.name] = val
        return values_by_name
