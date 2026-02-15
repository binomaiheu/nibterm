"""Dialog for managing variable definitions (name, source, unit, extraction).

Serial parser mode is configured in Serial settings, not here. This dialog
only edits variables and shows extraction details according to the current
serial (or per-topic MQTT) parser config.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Callable

from PySide6.QtCore import Qt, SignalInstance
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from ..config.variable import SerialParserConfig, VariableDefinition
from ..data.json_utils import unique_variable_name
from ..data.transforms import get_expression_variable_names, rewrite_expression_rename


class VariableEditDialog(QDialog):
    """Sub-dialog for adding a transform variable or editing name/unit/expression."""

    def __init__(
        self,
        variable: VariableDefinition | None = None,
        serial_mode: str = "csv",
        existing_names: set[str] | None = None,
        all_variable_names: list[str] | None = None,
        transform_only: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._existing_names = existing_names or set()
        self._editing_name = variable.name if variable else ""
        self._transform_only = transform_only
        self._editing_variable = deepcopy(variable) if variable else None

        if transform_only:
            self.setWindowTitle("Add transform variable")
        elif variable and variable.source == "transform":
            self.setWindowTitle("Edit transform variable")
        else:
            self.setWindowTitle("Edit variable")

        self._name_edit = QLineEdit()
        self._unit_edit = QLineEdit()
        self._unit_edit.setPlaceholderText("e.g. °C, V, %")

        self._source_combo = QComboBox()
        self._source_combo.addItem("Serial", "serial")
        self._source_combo.addItem("MQTT", "mqtt")
        self._source_combo.addItem("Transform", "transform")

        # Serial fields
        self._csv_column_spin = QSpinBox()
        self._csv_column_spin.setRange(0, 999)
        self._serial_json_path_edit = QLineEdit()
        self._serial_json_path_edit.setPlaceholderText("e.g. $.sensors.temperature")
        self._regex_pattern_edit = QLineEdit()
        self._regex_pattern_edit.setPlaceholderText("e.g. temp=(\\d+\\.\\d+)")
        self._regex_group_spin = QSpinBox()
        self._regex_group_spin.setRange(0, 99)
        self._regex_group_spin.setValue(1)

        # MQTT fields
        self._mqtt_topic_edit = QLineEdit()
        self._mqtt_topic_edit.setPlaceholderText("e.g. sensors/room1")
        self._mqtt_json_path_edit = QLineEdit()
        self._mqtt_json_path_edit.setPlaceholderText("e.g. $.temperature")

        # Transform fields
        self._expression_edit = QLineEdit()
        self._expression_edit.setPlaceholderText("e.g. temp_raw * 0.01")
        self._available_vars_label = QLabel()
        if all_variable_names:
            self._available_vars_label.setText(
                "Available: " + ", ".join(all_variable_names)
            )
            self._available_vars_label.setWordWrap(True)
            self._available_vars_label.setStyleSheet("color: gray; font-size: 0.9em;")

        # Serial extraction group
        self._serial_group = QGroupBox("Serial extraction")
        serial_form = QFormLayout(self._serial_group)
        self._csv_row_label = QLabel("CSV column")
        serial_form.addRow(self._csv_row_label, self._csv_column_spin)
        self._serial_json_label = QLabel("JSON path")
        serial_form.addRow(self._serial_json_label, self._serial_json_path_edit)
        self._regex_pattern_label = QLabel("Regex pattern")
        serial_form.addRow(self._regex_pattern_label, self._regex_pattern_edit)
        self._regex_group_label = QLabel("Regex group")
        serial_form.addRow(self._regex_group_label, self._regex_group_spin)

        # MQTT extraction group
        self._mqtt_group = QGroupBox("MQTT extraction")
        mqtt_form = QFormLayout(self._mqtt_group)
        mqtt_form.addRow("Topic", self._mqtt_topic_edit)
        mqtt_form.addRow("JSON path", self._mqtt_json_path_edit)

        # Transform group
        self._transform_group = QGroupBox("Transform expression")
        transform_form = QFormLayout(self._transform_group)
        transform_form.addRow("Expression", self._expression_edit)
        transform_form.addRow(self._available_vars_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        self._name_unit_only = (
            variable is not None
            and variable.source in ("serial", "mqtt")
        )

        form = QFormLayout()
        form.addRow("Name", self._name_edit)
        form.addRow("Unit", self._unit_edit)
        if not self._transform_only and not self._name_unit_only:
            form.addRow("Source", self._source_combo)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._serial_group)
        layout.addWidget(self._mqtt_group)
        layout.addWidget(self._transform_group)
        layout.addWidget(buttons)

        self._serial_mode = serial_mode
        self._source_combo.currentIndexChanged.connect(self._update_visibility)

        # Load existing variable
        if variable:
            self._name_edit.setText(variable.name)
            self._unit_edit.setText(variable.unit)
            idx = self._source_combo.findData(variable.source)
            if idx >= 0:
                self._source_combo.setCurrentIndex(idx)
            self._csv_column_spin.setValue(variable.csv_column)
            self._serial_json_path_edit.setText(variable.json_path)
            self._regex_pattern_edit.setText(variable.regex_pattern)
            self._regex_group_spin.setValue(variable.regex_group)
            self._mqtt_topic_edit.setText(variable.mqtt_topic)
            self._mqtt_json_path_edit.setText(variable.json_path)
            self._expression_edit.setText(variable.expression)

        self._update_visibility()

        if self._transform_only or (
            self._editing_variable and self._editing_variable.source == "transform"
        ):
            self.setMinimumWidth(440)
            self.setMinimumHeight(220)

    def _update_visibility(self) -> None:
        if self._name_unit_only:
            self._serial_group.setVisible(False)
            self._mqtt_group.setVisible(False)
            self._transform_group.setVisible(False)
        elif self._transform_only or (
            self._editing_variable and self._editing_variable.source == "transform"
        ):
            self._serial_group.setVisible(False)
            self._mqtt_group.setVisible(False)
            self._transform_group.setVisible(True)
        else:
            source = self._source_combo.currentData()
            self._serial_group.setVisible(source == "serial")
            self._mqtt_group.setVisible(source == "mqtt")
            self._transform_group.setVisible(source == "transform")
            # Within serial, show only fields relevant to serial parser mode
            is_csv = self._serial_mode == "csv"
            is_json = self._serial_mode == "json"
            is_regex = self._serial_mode == "regex"
            self._csv_column_spin.setVisible(is_csv)
            self._csv_row_label.setVisible(is_csv)
            self._serial_json_path_edit.setVisible(is_json)
            self._serial_json_label.setVisible(is_json)
            self._regex_pattern_edit.setVisible(is_regex)
            self._regex_pattern_label.setVisible(is_regex)
            self._regex_group_spin.setVisible(is_regex)
            self._regex_group_label.setVisible(is_regex)

        self.adjustSize()

    def _validate_and_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Variable name is required.")
            return
        # Ensure name is unique (allow same name if editing existing)
        if name != self._editing_name and name in self._existing_names:
            QMessageBox.warning(self, "Validation", f"Variable name '{name}' already exists.")
            return
        self.accept()

    def variable(self) -> VariableDefinition:
        name = self._name_edit.text().strip()
        unit = self._unit_edit.text().strip()
        if self._name_unit_only and self._editing_variable:
            return replace(
                self._editing_variable,
                name=name,
                unit=unit,
            )
        if self._transform_only or (
            self._editing_variable and self._editing_variable.source == "transform"
        ):
            return VariableDefinition(
                name=name,
                source="transform",
                unit=unit,
                expression=self._expression_edit.text().strip(),
            )
        source = self._source_combo.currentData()
        json_path = ""
        if source == "serial":
            json_path = self._serial_json_path_edit.text().strip()
        elif source == "mqtt":
            json_path = self._mqtt_json_path_edit.text().strip()
        return VariableDefinition(
            name=name,
            source=source,
            unit=unit,
            csv_column=self._csv_column_spin.value(),
            json_path=json_path,
            regex_pattern=self._regex_pattern_edit.text().strip(),
            regex_group=self._regex_group_spin.value(),
            mqtt_topic=self._mqtt_topic_edit.text().strip(),
            expression=self._expression_edit.text().strip(),
        )


class VariablesDialog(QDialog):
    """Main dialog for managing all variable definitions."""

    def __init__(
        self,
        variables: list[VariableDefinition],
        serial_config: SerialParserConfig,
        get_values: Callable[[], dict[str, float]] | None = None,
        values_updated_signal: SignalInstance | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Variables")
        self.setMinimumWidth(650)
        self._variables = [deepcopy(v) for v in variables]
        self._original_names = [v.name for v in variables]  # for value lookup after rename
        self._serial_config = deepcopy(serial_config)  # read-only: for details & Add/Edit
        self._get_values = get_values
        self._values_updated_signal = values_updated_signal

        # -- Variables table (no Serial Parser section; config is in Serial menu/settings) --
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Source", "Source config", "Name", "Unit", "Value"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        btn_add_transform = QPushButton("Add transform...")
        btn_edit = QPushButton("Edit...")
        btn_remove = QPushButton("Remove")
        btn_add_transform.clicked.connect(self._on_add_transform)
        btn_edit.clicked.connect(self._on_edit)
        btn_remove.clicked.connect(self._on_remove)
        self._table.doubleClicked.connect(self._on_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_add_transform)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Define variables in the Serial and MQTT tabs. Here you can set units, "
                "rename, remove, or add transform variables (formulas from existing variables)."
            )
        )
        layout.addWidget(QLabel("Defined variables:"))
        layout.addWidget(self._table)
        layout.addLayout(btn_layout)
        layout.addWidget(buttons)

        self._refresh_table()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._values_updated_signal is not None:
            self._values_updated_signal.connect(
                self._refresh_table, Qt.ConnectionType.QueuedConnection
            )
        # Refresh immediately so serial and transform values are current when dialog opens
        self._refresh_table()

    def hideEvent(self, event: QHideEvent) -> None:
        if self._values_updated_signal is not None:
            try:
                self._values_updated_signal.disconnect(self._refresh_table)
            except (TypeError, RuntimeError):
                pass
        super().hideEvent(event)

    def _refresh_table(self) -> None:
        serial_mode = self._serial_config.mode
        values = self._get_values() if self._get_values else {}
        self._table.setRowCount(len(self._variables))
        for row, v in enumerate(self._variables):
            self._table.setItem(row, 0, QTableWidgetItem(v.source))
            self._table.setItem(row, 1, QTableWidgetItem(v.details_summary(serial_mode)))
            self._table.setItem(row, 2, QTableWidgetItem(v.name))
            self._table.setItem(row, 3, QTableWidgetItem(v.unit))
            # Use current name first; if renamed in this session, fall back to original name
            val = values.get(v.name)
            if (
                val is None
                and len(self._original_names) == len(self._variables)
                and row < len(self._original_names)
                and self._original_names[row] != v.name
            ):
                val = values.get(self._original_names[row])
            if val is not None:
                try:
                    value_text = f"{float(val):.6g}".rstrip("0").rstrip(".")
                except (TypeError, ValueError):
                    value_text = str(val)
            else:
                value_text = "—"
            self._table.setItem(row, 4, QTableWidgetItem(value_text))

    def _on_add_transform(self) -> None:
        existing = {v.name for v in self._variables}
        all_names = [v.name for v in self._variables]
        dlg = VariableEditDialog(
            variable=None,
            serial_mode=self._serial_config.mode,
            existing_names=existing,
            all_variable_names=all_names,
            transform_only=True,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_var = dlg.variable()
            new_var.name = unique_variable_name(new_var.name or "transform", existing)
            self._variables.append(new_var)
            self._refresh_table()

    def _on_edit(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._variables):
            return
        var = self._variables[row]
        existing = {v.name for v in self._variables}
        all_names = [v.name for v in self._variables if v.name != var.name]
        dlg = VariableEditDialog(
            variable=var,
            serial_mode=self._serial_config.mode,
            existing_names=existing,
            all_variable_names=all_names,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_var = dlg.variable()
            old_name = var.name
            self._variables[row] = new_var
            # Update transform expressions that reference the renamed variable
            if old_name != new_var.name:
                for i, v in enumerate(self._variables):
                    if v.source == "transform" and v.expression:
                        refs = get_expression_variable_names(v.expression)
                        if old_name in refs:
                            new_expr = rewrite_expression_rename(
                                v.expression, old_name, new_var.name
                            )
                            self._variables[i] = replace(v, expression=new_expr)
            self._refresh_table()

    def _on_remove(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._variables):
            return
        self._variables.pop(row)
        self._refresh_table()

    def variables(self) -> list[VariableDefinition]:
        return [deepcopy(v) for v in self._variables]
