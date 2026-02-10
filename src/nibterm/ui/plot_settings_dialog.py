from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from .plot_panel import PlotConfig, TransformExpression


class PlotSettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plot Settings")

        self._mode = QComboBox()
        self._mode.addItem("Time series", "timeseries")
        self._mode.addItem("X/Y", "xy")
        self._delimiter = QLineEdit()
        self._series_list = QListWidget()
        self._series_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._xy_x_combo = QComboBox()
        self._xy_y_combo = QComboBox()
        self._name_count = QSpinBox()
        self._name_count.setRange(1, 64)
        self._names_table = QTableWidget(0, 2)
        self._names_table.setHorizontalHeaderLabels(["Index", "Name"])
        self._names_table.verticalHeader().setVisible(False)
        self._names_table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        self._transform_table = QTableWidget(0, 2)
        self._transform_table.setHorizontalHeaderLabels(["Name", "Expression"])
        self._transform_table.verticalHeader().setVisible(False)
        self._transform_add = QPushButton("Add")
        self._transform_remove = QPushButton("Remove")
        self._buffer_size = QSpinBox()
        self._buffer_size.setRange(10, 100_000)
        self._update_ms = QSpinBox()
        self._update_ms.setRange(10, 2000)

        parsing_group = QGroupBox("Parsing")
        parsing_form = QFormLayout(parsing_group)
        parsing_form.addRow("Delimiter", self._delimiter)
        parsing_form.addRow("Name rows", self._name_count)
        parsing_form.addRow(self._names_table)

        transform_group = QGroupBox("Transformations")
        transform_form = QFormLayout(transform_group)
        transform_buttons = QHBoxLayout()
        transform_buttons.addWidget(self._transform_add)
        transform_buttons.addWidget(self._transform_remove)
        transform_buttons.addStretch(1)
        transform_form.addRow(self._transform_table)
        transform_form.addRow("", transform_buttons)
        self._transform_help = QLabel(
            "Expressions can use c0, c1 or column names; functions: sin, cos, sqrt, log."
        )
        self._transform_help.setWordWrap(True)
        transform_form.addRow("", self._transform_help)

        plot_group = QGroupBox("Plotting")
        plot_form = QFormLayout(plot_group)
        plot_form.addRow("Mode", self._mode)
        self._series_label = QLabel("Series variables")
        plot_form.addRow(self._series_label, self._series_list)
        self._xy_x_label = QLabel("X variable")
        self._xy_y_label = QLabel("Y variable")
        plot_form.addRow(self._xy_x_label, self._xy_x_combo)
        plot_form.addRow(self._xy_y_label, self._xy_y_combo)
        plot_form.addRow("Buffer size", self._buffer_size)
        plot_form.addRow("Update interval (ms)", self._update_ms)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(parsing_group)
        layout.addWidget(transform_group)
        layout.addWidget(plot_group)
        layout.addWidget(buttons)

        self._mode.currentIndexChanged.connect(self._update_mode_fields)
        self._name_count.valueChanged.connect(self._rebuild_name_rows)
        self._names_table.itemChanged.connect(self._refresh_variable_lists)
        self._transform_add.clicked.connect(self._add_transform_row)
        self._transform_remove.clicked.connect(self._remove_transform_row)
        self._transform_table.itemChanged.connect(self._refresh_variable_lists)
        self._update_mode_fields()

    def load(self, config: PlotConfig) -> None:
        self._mode.setCurrentIndex(
            0 if config.mode == "timeseries" else 1
        )
        self._delimiter.setText(config.delimiter)
        self._name_count.setValue(_max_name_index(config) + 1)
        self._rebuild_name_rows()
        self._apply_names(config.column_names)
        self._load_transform_table(config.transform_expressions)
        self._buffer_size.setValue(config.buffer_size)
        self._update_ms.setValue(config.update_ms)
        self._refresh_variable_lists()
        self._apply_variable_selection(config)
        self._update_mode_fields()

    def config(self) -> PlotConfig:
        column_names = self._collect_names()
        transforms = self._collect_transforms()
        return PlotConfig(
            mode=self._mode.currentData(),
            delimiter=self._delimiter.text() or ",",
            columns=[int(key[1:]) for key in self._selected_raw_columns()],
            column_names=column_names,
            transform_expressions=transforms,
            series_variables=self._selected_series_variables(),
            xy_x_var=self._xy_x_combo.currentData() or "c0",
            xy_y_var=self._xy_y_combo.currentData() or "c1",
            buffer_size=self._buffer_size.value(),
            update_ms=self._update_ms.value(),
        )

    def _update_mode_fields(self) -> None:
        is_timeseries = self._mode.currentData() == "timeseries"
        self._series_list.setVisible(is_timeseries)
        self._series_label.setVisible(is_timeseries)
        self._xy_x_combo.setVisible(not is_timeseries)
        self._xy_y_combo.setVisible(not is_timeseries)
        self._xy_x_label.setVisible(not is_timeseries)
        self._xy_y_label.setVisible(not is_timeseries)

    def _rebuild_name_rows(self) -> None:
        count = self._name_count.value()
        self._names_table.setRowCount(count)
        for row in range(count):
            index_item = QTableWidgetItem(str(row))
            index_item.setFlags(index_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._names_table.setItem(row, 0, index_item)
            if self._names_table.item(row, 1) is None:
                self._names_table.setItem(row, 1, QTableWidgetItem(""))

    def _apply_names(self, names: dict[int, str]) -> None:
        for idx, name in names.items():
            if idx >= self._names_table.rowCount():
                continue
            item = self._names_table.item(idx, 1)
            if item is None:
                item = QTableWidgetItem()
                self._names_table.setItem(idx, 1, item)
            item.setText(name)

    def _collect_names(self) -> dict[int, str]:
        names: dict[int, str] = {}
        for row in range(self._names_table.rowCount()):
            item = self._names_table.item(row, 1)
            if item is None:
                continue
            name = item.text().strip()
            if name:
                names[row] = name
        return names

    def _add_transform_row(self) -> None:
        row = self._transform_table.rowCount()
        self._transform_table.insertRow(row)
        self._transform_table.setItem(row, 0, QTableWidgetItem(""))
        self._transform_table.setItem(row, 1, QTableWidgetItem(""))
        self._refresh_variable_lists()

    def _remove_transform_row(self) -> None:
        row = self._transform_table.currentRow()
        if row >= 0:
            self._transform_table.removeRow(row)
            self._refresh_variable_lists()

    def _load_transform_table(self, transforms: list[TransformExpression]) -> None:
        self._transform_table.setRowCount(0)
        for transform in transforms:
            row = self._transform_table.rowCount()
            self._transform_table.insertRow(row)
            self._transform_table.setItem(row, 0, QTableWidgetItem(transform.name))
            self._transform_table.setItem(row, 1, QTableWidgetItem(transform.expr))

    def _collect_transforms(self) -> list[TransformExpression]:
        transforms: list[TransformExpression] = []
        for row in range(self._transform_table.rowCount()):
            name_item = self._transform_table.item(row, 0)
            expr_item = self._transform_table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            expr = expr_item.text().strip() if expr_item else ""
            if not expr:
                continue
            if not name:
                name = expr
            transforms.append(TransformExpression(name=name, expr=expr))
        return transforms

    def _available_variables(self) -> list[tuple[str, str]]:
        variables: list[tuple[str, str]] = []
        names = self._collect_names()
        for idx in range(self._names_table.rowCount()):
            key = f"c{idx}"
            label = names.get(idx, key)
            display = f"{label} ({key})" if label != key else label
            variables.append((key, display))
        for transform in self._collect_transforms():
            variables.append((transform.name, f"{transform.name} (fx)"))
        return variables

    def _refresh_variable_lists(self) -> None:
        variables = self._available_variables()
        self._series_list.blockSignals(True)
        self._series_list.clear()
        for key, display in variables:
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._series_list.addItem(item)
        self._series_list.blockSignals(False)

        self._xy_x_combo.blockSignals(True)
        self._xy_y_combo.blockSignals(True)
        self._xy_x_combo.clear()
        self._xy_y_combo.clear()
        for key, display in variables:
            self._xy_x_combo.addItem(display, key)
            self._xy_y_combo.addItem(display, key)
        self._xy_x_combo.blockSignals(False)
        self._xy_y_combo.blockSignals(False)

    def _apply_variable_selection(self, config: PlotConfig) -> None:
        series_vars = config.series_variables or [f"c{idx}" for idx in config.columns]
        for row in range(self._series_list.count()):
            item = self._series_list.item(row)
            key = item.data(Qt.ItemDataRole.UserRole)
            if key in series_vars:
                item.setSelected(True)
        self._select_combo_by_data(self._xy_x_combo, config.xy_x_var)
        self._select_combo_by_data(self._xy_y_combo, config.xy_y_var)

    def _select_combo_by_data(self, combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.count() > 0:
            combo.setCurrentIndex(0)

    def _selected_series_variables(self) -> list[str]:
        vars_selected: list[str] = []
        for item in self._series_list.selectedItems():
            key = item.data(Qt.ItemDataRole.UserRole)
            if key:
                vars_selected.append(key)
        if not vars_selected and self._series_list.count() > 0:
            first = self._series_list.item(0)
            key = first.data(Qt.ItemDataRole.UserRole)
            if key:
                vars_selected.append(key)
        return vars_selected

    def _selected_raw_columns(self) -> list[str]:
        raw: list[str] = []
        for key in self._selected_series_variables():
            if key.startswith("c") and key[1:].isdigit():
                raw.append(key)
        return raw


def _parse_int(text: str, default: int) -> int:
    try:
        return int(text.strip())
    except (ValueError, AttributeError):
        return default


def _max_name_index(config: PlotConfig) -> int:
    indices = list(config.column_names.keys())
    indices.extend(config.columns)
    indices.append(config.x_column)
    indices.append(config.y_column)
    for var in config.series_variables:
        if var.startswith("c") and var[1:].isdigit():
            indices.append(int(var[1:]))
    for var in (config.xy_x_var, config.xy_y_var):
        if var.startswith("c") and var[1:].isdigit():
            indices.append(int(var[1:]))
    return max(indices) if indices else 0


def _serialize_transform(transforms: list[TransformExpression]) -> str:
    parts: list[str] = []
    for transform in transforms:
        if transform.name and transform.name != transform.expr:
            parts.append(f"{transform.name}={transform.expr}")
        else:
            parts.append(transform.expr)
    return "; ".join(parts)
