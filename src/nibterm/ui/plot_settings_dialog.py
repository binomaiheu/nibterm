from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from .plot_panel import PlotConfig, TransformExpression


class PlotSettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Data Pipeline")

        self._delimiter = QLineEdit()
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

        parsing_group = QGroupBox("Parsing")
        parsing_layout = QVBoxLayout(parsing_group)
        parsing_form = QHBoxLayout()
        parsing_form.addWidget(QLabel("Delimiter"))
        parsing_form.addWidget(self._delimiter)
        parsing_form.addWidget(QLabel("Name rows"))
        parsing_form.addWidget(self._name_count)
        parsing_layout.addLayout(parsing_form)
        parsing_layout.addWidget(self._names_table)

        transform_group = QGroupBox("Transformations")
        transform_layout = QVBoxLayout(transform_group)
        transform_layout.addWidget(self._transform_table)
        transform_buttons = QHBoxLayout()
        transform_buttons.addWidget(self._transform_add)
        transform_buttons.addWidget(self._transform_remove)
        transform_buttons.addStretch(1)
        transform_layout.addLayout(transform_buttons)
        self._transform_help = QLabel(
            "Expressions can use c0, c1 or column names; functions: sin, cos, sqrt, log."
        )
        self._transform_help.setWordWrap(True)
        transform_layout.addWidget(self._transform_help)

        self._tabs = QTabWidget()
        self._tabs.addTab(parsing_group, "Parsing")
        self._tabs.addTab(transform_group, "Transformations")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addWidget(buttons)

        self._name_count.valueChanged.connect(self._rebuild_name_rows)
        self._transform_add.clicked.connect(self._add_transform_row)
        self._transform_remove.clicked.connect(self._remove_transform_row)
        self._transform_table.itemChanged.connect(self._noop)

    def load(self, config: PlotConfig) -> None:
        self._delimiter.setText(config.delimiter)
        self._name_count.setValue(_max_name_index(config) + 1)
        self._rebuild_name_rows()
        self._apply_names(config.column_names)
        self._load_transform_table(config.transform_expressions)

    def config(self) -> PlotConfig:
        column_names = self._collect_names()
        transforms = self._collect_transforms()
        return PlotConfig(
            delimiter=self._delimiter.text() or ",",
            column_names=column_names,
            transform_expressions=transforms,
        )

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
        self._noop()

    def _remove_transform_row(self) -> None:
        row = self._transform_table.currentRow()
        if row >= 0:
            self._transform_table.removeRow(row)
        self._noop()

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

    def _noop(self) -> None:
        return


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
