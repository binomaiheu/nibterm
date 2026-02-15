"""Collapsible Serial Plot variables panel: last line display with click-to-add CSV or JSON."""
from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings, Qt, Slot
from PySide6.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config.variable import VariableDefinition
from ..data.json_utils import (
    build_json_with_path_ranges,
    sanitize_var_name,
    unique_variable_name,
)
from .clickable_display import PathClickableEdit, build_csv_column_ranges

if TYPE_CHECKING:
    from ..data.variable_manager import VariableManager

_SETTINGS_KEY_EXPANDED = "ui/serial_plot_panel_expanded"


class SerialPlotPanel(QWidget):
    """Collapsible panel below the terminal: last serial line (clickable when CSV) and serial variables table."""

    def __init__(self, variable_manager: "VariableManager", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._variable_manager = variable_manager
        self._content_widget: QWidget | None = None
        self._last_line_display: PathClickableEdit | None = None
        self._last_line_label: QLabel | None = None
        self._plot_table: QTableWidget | None = None
        self._toggle_btn: QPushButton | None = None
        self._cached_json_display: str = ""
        self._cached_json_path_ranges: list[tuple[int, int, str, str]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)

        self._toggle_btn = QPushButton("Plot variables \u25BC")  # ▼
        self._toggle_btn.setStyleSheet("text-align: left; padding-left: 6px;")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(False)
        expanded = QSettings().value(_SETTINGS_KEY_EXPANDED, False, type=bool)
        self._toggle_btn.setChecked(expanded)
        self._toggle_btn.clicked.connect(self._on_toggle_clicked)
        layout.addWidget(self._toggle_btn)

        self._content_widget = QWidget()
        content_layout = QVBoxLayout(self._content_widget)
        content_layout.setContentsMargins(0, 4, 0, 4)

        self._last_line_label = QLabel("Last line (click a value to add as plot variable):")
        content_layout.addWidget(self._last_line_label)
        self._last_line_display = PathClickableEdit()
        self._last_line_display.setReadOnly(True)
        self._last_line_display.setPlaceholderText(
            "Last serial line will appear here. Set parser to CSV or JSON and click a value to add variables."
        )
        self._last_line_display.set_on_path_clicked(self._on_value_clicked)
        self._last_line_display.setMinimumHeight(28)
        self._last_line_display.setMaximumHeight(60)
        content_layout.addWidget(self._last_line_display)

        content_layout.addWidget(QLabel("Serial plot variables:"))
        self._plot_table = QTableWidget(0, 3)
        self._plot_table.setHorizontalHeaderLabels(
            ["Extraction", "Variable name", "Value"]
        )
        self._plot_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._plot_table.itemChanged.connect(self._on_serial_plot_table_item_changed)
        content_layout.addWidget(self._plot_table)

        btn_row = QHBoxLayout()
        self._plot_add = QPushButton("Add")
        self._plot_remove = QPushButton("Remove")
        self._plot_clear_all = QPushButton("Clear all")
        self._plot_add.clicked.connect(self._on_add)
        self._plot_remove.clicked.connect(self._on_remove)
        self._plot_clear_all.clicked.connect(self._on_clear_all)
        btn_row.addWidget(self._plot_add)
        btn_row.addWidget(self._plot_remove)
        btn_row.addWidget(self._plot_clear_all)
        btn_row.addStretch()
        content_layout.addLayout(btn_row)

        layout.addWidget(self._content_widget)

        self._content_widget.setVisible(expanded)
        self._update_toggle_text()

        self._variable_manager.values_updated.connect(self._refresh_table_from_manager)
        self._variable_manager.variables_changed.connect(self._refresh_table_from_manager)

        self._refresh_last_line()
        self._refresh_table_from_manager()

    def _update_toggle_text(self) -> None:
        if self._toggle_btn is None:
            return
        if self._toggle_btn.isChecked():
            self._toggle_btn.setText("Plot variables \u25BC")  # ▼
        else:
            self._toggle_btn.setText("Plot variables \u25B6")  # ▶

    def _on_toggle_clicked(self) -> None:
        expanded = self._toggle_btn.isChecked() if self._toggle_btn else False
        if self._content_widget is not None:
            self._content_widget.setVisible(expanded)
        self._update_toggle_text()
        QSettings().setValue(_SETTINGS_KEY_EXPANDED, expanded)

    def _refresh_last_line(self) -> None:
        if self._last_line_display is None or self._last_line_label is None:
            return
        line = (self._variable_manager.get_last_serial_line() or "").strip()
        cfg = self._variable_manager.serial_config
        serial_vars = self._variable_manager.get_serial_variables()

        if cfg.mode == "json":
            self._last_line_label.setText("Last line (click a JSON value to add as plot variable):")
            self._last_line_display.setMaximumBlockCount(0)
            self._last_line_display.setMinimumHeight(28)
            self._last_line_display.setMaximumHeight(400)
            text = line
            prefix = (cfg.json_prefix or "").strip()
            if prefix and text.startswith(prefix):
                text = text[len(prefix) :].strip()
            try:
                obj = json.loads(text)
                display, path_ranges = build_json_with_path_ranges(obj)
                self._cached_json_display = display
                self._cached_json_path_ranges = path_ranges
                self._last_line_display.setPlainText(display)
                self._last_line_display.set_path_ranges(path_ranges)
            except (json.JSONDecodeError, TypeError, ValueError):
                self._last_line_display.setPlainText(self._cached_json_display)
                self._last_line_display.set_path_ranges(self._cached_json_path_ranges)
            paths = {v.json_path for v in serial_vars if v.json_path}
            self._last_line_display.set_plot_variable_paths(paths)
        elif cfg.mode == "csv":
            self._last_line_label.setText("Last line (click a CSV column to add as plot variable):")
            self._last_line_display.setMaximumBlockCount(1)
            self._last_line_display.setMinimumHeight(28)
            self._last_line_display.setMaximumHeight(60)
            self._last_line_display.setPlainText(line)
            if line:
                ranges = build_csv_column_ranges(line, cfg.csv_delimiter or ",")
                self._last_line_display.set_path_ranges(ranges)
                paths = {f"__column_{v.csv_column}" for v in serial_vars}
                self._last_line_display.set_plot_variable_paths(paths)
            else:
                self._last_line_display.set_path_ranges([])
                self._last_line_display.set_plot_variable_paths(set())
        else:
            self._last_line_label.setText("Last line (raw):")
            self._last_line_display.setMaximumBlockCount(1)
            self._last_line_display.setMinimumHeight(28)
            self._last_line_display.setMaximumHeight(60)
            self._last_line_display.setPlainText(line)
            self._last_line_display.set_path_ranges([])
            self._last_line_display.set_plot_variable_paths(set())

    def _refresh_table_from_manager(self) -> None:
        if self._plot_table is None:
            return
        self._plot_table.blockSignals(True)
        try:
            serial_vars = self._variable_manager.get_serial_variables()
            values = self._variable_manager.get_values()
            serial_mode = self._variable_manager.serial_config.mode
            self._plot_table.setRowCount(len(serial_vars))
            for row, v in enumerate(serial_vars):
                if serial_mode == "json" and v.json_path:
                    ext = v.json_path
                elif serial_mode == "regex" and v.regex_pattern:
                    ext = f"{v.regex_pattern} (group {v.regex_group})"
                else:
                    ext = f"column {v.csv_column}"
                ext_item = QTableWidgetItem(ext)
                ext_item.setFlags(ext_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._plot_table.setItem(row, 0, ext_item)
                self._plot_table.setItem(row, 1, QTableWidgetItem(v.name))
                val = values.get(v.name)
                val_item = QTableWidgetItem("" if val is None else f"{val}")
                val_item.setFlags(val_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._plot_table.setItem(row, 2, val_item)
        finally:
            self._plot_table.blockSignals(False)
        self._refresh_last_line()

    def _on_serial_plot_table_item_changed(self, item: QTableWidgetItem) -> None:
        """Sync Variable name edits from the table back to the VariableManager."""
        if item.column() != 1:
            return
        row = item.row()
        serial_vars = self._variable_manager.get_serial_variables()
        if row < 0 or row >= len(serial_vars):
            return
        old_var = serial_vars[row]
        new_name = (item.text() or "").strip()
        if not new_name or new_name == old_var.name:
            return
        new_var = replace(old_var, name=new_name)
        self._variable_manager.update_variable(old_var.name, new_var)

    @Slot()
    def _on_value_clicked(self, path: str, key_name: str) -> None:
        cfg = self._variable_manager.serial_config
        serial_vars = self._variable_manager.get_serial_variables()
        existing = {v.name for v in self._variable_manager.variables}

        if path.startswith("__column_"):
            if cfg.mode != "csv":
                return
            try:
                col = int(path.replace("__column_", ""))
            except ValueError:
                return
            if any(v.csv_column == col for v in serial_vars):
                return
            name = unique_variable_name(f"col{col}", existing)
            self._variable_manager.add_variable(
                VariableDefinition(name=name, source="serial", csv_column=col)
            )
        else:
            if cfg.mode != "json":
                return
            if any(v.json_path == path for v in serial_vars):
                return
            base = sanitize_var_name(key_name) if key_name else "value"
            name = unique_variable_name(base, existing)
            self._variable_manager.add_variable(
                VariableDefinition(name=name, source="serial", json_path=path)
            )

    def _on_add(self) -> None:
        cfg = self._variable_manager.serial_config
        serial_vars = self._variable_manager.get_serial_variables()
        existing = {v.name for v in self._variable_manager.variables}
        if cfg.mode == "json":
            name = unique_variable_name("value", existing)
            self._variable_manager.add_variable(
                VariableDefinition(name=name, source="serial", json_path="$")
            )
        else:
            columns_used = {v.csv_column for v in serial_vars}
            col = 0
            while col in columns_used:
                col += 1
            name = unique_variable_name(f"col{col}", existing)
            self._variable_manager.add_variable(
                VariableDefinition(name=name, source="serial", csv_column=col)
            )

    def _on_remove(self) -> None:
        if self._plot_table is None:
            return
        row = self._plot_table.currentRow()
        if row < 0:
            return
        name_item = self._plot_table.item(row, 1)
        if name_item is None:
            return
        name = name_item.text().strip()
        if name:
            self._variable_manager.remove_variable(name)

    def _on_clear_all(self) -> None:
        self._variable_manager.remove_all_serial_variables()
