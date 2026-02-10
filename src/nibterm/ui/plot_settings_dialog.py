from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
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
        self._columns = QLineEdit()
        self._x_column = QLineEdit()
        self._y_column = QLineEdit()
        self._name_count = QSpinBox()
        self._name_count.setRange(1, 64)
        self._names_table = QTableWidget(0, 2)
        self._names_table.setHorizontalHeaderLabels(["Index", "Name"])
        self._names_table.verticalHeader().setVisible(False)
        self._names_table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        self._transform = QLineEdit()
        self._transform.setPlaceholderText("e.g. Vbatt=c6; Power=Vbatt*c2")
        self._buffer_size = QSpinBox()
        self._buffer_size.setRange(10, 100_000)
        self._update_ms = QSpinBox()
        self._update_ms.setRange(10, 2000)

        form = QFormLayout()
        form.addRow("Mode", self._mode)
        form.addRow("Delimiter", self._delimiter)
        self._columns_label = QLabel("Columns (e.g. 0,1,2)")
        form.addRow(self._columns_label, self._columns)
        self._x_column_label = QLabel("X column (X/Y mode)")
        self._y_column_label = QLabel("Y column (X/Y mode)")
        form.addRow(self._x_column_label, self._x_column)
        form.addRow(self._y_column_label, self._y_column)
        form.addRow("Name rows", self._name_count)
        form.addRow(self._names_table)
        form.addRow("Transform expressions", self._transform)
        self._transform_help = QLabel(
            "Examples: Vbatt=c6; Power=Vbatt*c2; Temp=(c1-32)*5/9"
        )
        self._transform_help.setWordWrap(True)
        form.addRow("", self._transform_help)
        form.addRow("Buffer size", self._buffer_size)
        form.addRow("Update interval (ms)", self._update_ms)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._mode.currentIndexChanged.connect(self._update_mode_fields)
        self._name_count.valueChanged.connect(self._rebuild_name_rows)
        self._update_mode_fields()

    def load(self, config: PlotConfig) -> None:
        self._mode.setCurrentIndex(
            0 if config.mode == "timeseries" else 1
        )
        self._delimiter.setText(config.delimiter)
        self._columns.setText(",".join(str(c) for c in config.columns))
        self._x_column.setText(str(config.x_column))
        self._y_column.setText(str(config.y_column))
        self._name_count.setValue(_max_name_index(config) + 1)
        self._rebuild_name_rows()
        self._apply_names(config.column_names)
        self._transform.setText(_serialize_transform(config.transform_expressions))
        self._buffer_size.setValue(config.buffer_size)
        self._update_ms.setValue(config.update_ms)
        self._update_mode_fields()

    def config(self) -> PlotConfig:
        columns = _parse_int_list(self._columns.text(), [0])
        column_names = self._collect_names()
        transforms = _parse_transform_string(self._transform.text())
        return PlotConfig(
            mode=self._mode.currentData(),
            delimiter=self._delimiter.text() or ",",
            columns=columns,
            x_column=_parse_int(self._x_column.text(), 0),
            y_column=_parse_int(self._y_column.text(), 1),
            column_names=column_names,
            transform_expressions=transforms,
            buffer_size=self._buffer_size.value(),
            update_ms=self._update_ms.value(),
        )

    def _update_mode_fields(self) -> None:
        is_timeseries = self._mode.currentData() == "timeseries"
        self._columns.setVisible(is_timeseries)
        self._columns_label.setVisible(is_timeseries)
        self._x_column.setVisible(not is_timeseries)
        self._y_column.setVisible(not is_timeseries)
        self._x_column_label.setVisible(not is_timeseries)
        self._y_column_label.setVisible(not is_timeseries)

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


def _parse_int_list(text: str, default: list[int]) -> list[int]:
    values: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(int(part))
        except ValueError:
            continue
    return values or list(default)


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
    return max(indices) if indices else 0


def _serialize_transform(transforms: list[TransformExpression]) -> str:
    parts: list[str] = []
    for transform in transforms:
        if transform.name and transform.name != transform.expr:
            parts.append(f"{transform.name}={transform.expr}")
        else:
            parts.append(transform.expr)
    return "; ".join(parts)


def _parse_transform_string(text: str) -> list[TransformExpression]:
    transforms: list[TransformExpression] = []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" in chunk:
            name, expr = chunk.split("=", 1)
            name = name.strip()
            expr = expr.strip()
        else:
            name = chunk
            expr = chunk
        if expr:
            transforms.append(TransformExpression(name=name or expr, expr=expr))
    return transforms
