from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QFormLayout,
)

from ..config.plot_config import PlotConfig


class PlotSetupDialog(QDialog):
    def __init__(self, variables: list[tuple[str, str]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plot Setup")
        self._variables = variables

        self._mode = QComboBox()
        self._mode.addItem("Time series", "timeseries")
        self._mode.addItem("X/Y", "xy")

        self._series_list = QListWidget()
        self._series_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        self._x_combo = QComboBox()
        self._y_combo = QComboBox()

        self._buffer_size = QSpinBox()
        self._buffer_size.setRange(10, 100_000)
        self._update_ms = QSpinBox()
        self._update_ms.setRange(10, 5000)

        form = QFormLayout()
        form.addRow("Mode", self._mode)
        self._series_label = QLabel("Series variables")
        self._x_label = QLabel("X variable")
        self._y_label = QLabel("Y variable")
        form.addRow(self._series_label, self._series_list)
        form.addRow(self._x_label, self._x_combo)
        form.addRow(self._y_label, self._y_combo)
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
        self._populate_variables()
        self._update_mode_fields()

    def _populate_variables(self) -> None:
        self._series_list.clear()
        self._x_combo.clear()
        self._y_combo.clear()
        for key, label in self._variables:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._series_list.addItem(item)
            self._x_combo.addItem(label, key)
            self._y_combo.addItem(label, key)

    def load(self, config: PlotConfig) -> None:
        self._mode.setCurrentIndex(0 if config.mode == "timeseries" else 1)
        self._buffer_size.setValue(config.buffer_size)
        self._update_ms.setValue(config.update_ms)
        self._select_series_vars(config.series_variables)
        self._select_combo_by_data(self._x_combo, config.xy_x_var)
        self._select_combo_by_data(self._y_combo, config.xy_y_var)
        self._update_mode_fields()

    def config(self) -> PlotConfig:
        series_vars = self._selected_series_vars()
        config = PlotConfig()
        config.mode = self._mode.currentData()
        config.series_variables = series_vars
        config.xy_x_var = self._x_combo.currentData() or "c0"
        config.xy_y_var = self._y_combo.currentData() or "c1"
        config.buffer_size = self._buffer_size.value()
        config.update_ms = self._update_ms.value()
        return config

    def _update_mode_fields(self) -> None:
        is_timeseries = self._mode.currentData() == "timeseries"
        self._series_list.setVisible(is_timeseries)
        self._series_label.setVisible(is_timeseries)
        self._x_combo.setVisible(not is_timeseries)
        self._y_combo.setVisible(not is_timeseries)
        self._x_label.setVisible(not is_timeseries)
        self._y_label.setVisible(not is_timeseries)

    def _selected_series_vars(self) -> list[str]:
        vars_selected: list[str] = []
        for item in self._series_list.selectedItems():
            key = item.data(Qt.ItemDataRole.UserRole)
            if key:
                vars_selected.append(key)
        if not vars_selected and self._series_list.count() > 0:
            key = self._series_list.item(0).data(Qt.ItemDataRole.UserRole)
            if key:
                vars_selected.append(key)
        return vars_selected

    def _select_series_vars(self, variables: list[str]) -> None:
        for row in range(self._series_list.count()):
            item = self._series_list.item(row)
            key = item.data(Qt.ItemDataRole.UserRole)
            item.setSelected(key in variables)

    def _select_combo_by_data(self, combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.count() > 0:
            combo.setCurrentIndex(0)
