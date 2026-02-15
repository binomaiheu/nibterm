from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import Callable

import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..config.plot_config import PlotConfig

logger = logging.getLogger(__name__)


class PlotPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._config = PlotConfig()
        self._enabled = False
        self._series: dict[str, deque[tuple[float, float]]] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._sample_index = 0
        self._start_time: float | None = None
        self._buffer_size = self._config.buffer_size

        self._time_axis = TimeAxis(orientation="bottom")
        self._plot = pg.PlotWidget(axisItems={"bottom": self._time_axis})
        self._plot.setBackground("w")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._legend = self._plot.addLegend()
        self._curve_colors = ["#d32f2f", "#1976d2", "#388e3c", "#f57c00", "#7b1fa2"]
        self._variable_list_fn: Callable[[], list[tuple[str, str]]] | None = None
        for axis in ("bottom", "left"):
            ax = self._plot.getAxis(axis)
            ax.setPen(pg.mkPen(color="k"))
            ax.setTextPen(pg.mkPen(color="k"))
        self._plot.getAxis("bottom").enableAutoSIPrefix(False)
        self._update_axis_labels()

        layout = QVBoxLayout(self)
        layout.addWidget(self._plot)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_plot)
        self._timer.start(self._config.update_ms)

    def set_config(self, config: PlotConfig) -> None:
        self._config = config
        self._timer.setInterval(config.update_ms)
        self._time_axis.set_mode(config.mode)
        self._reset_plot()

    def update_config(self, config: PlotConfig) -> None:
        if self._buffer_size != config.buffer_size:
            self._resize_buffers(config.buffer_size)
            self._refresh_plot()
        if self._config.mode != config.mode:
            self._config = config
            self._timer.setInterval(config.update_ms)
            self._time_axis.set_mode(config.mode)
            self._reset_plot()
            return
        self._migrate_series_labels(self._config, config)
        self._config = config
        self._timer.setInterval(config.update_ms)
        self._time_axis.set_mode(config.mode)
        self._prune_removed_series()
        self._update_axis_labels()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_variable_list_fn(
        self, fn: Callable[[], list[tuple[str, str]]] | None
    ) -> None:
        """Set callback to resolve variable name -> display label (e.g. with unit)."""
        self._variable_list_fn = fn

    def _name_to_label(self) -> dict[str, str]:
        """Return map variable name -> display label for axis/legend."""
        if not self._variable_list_fn:
            return {}
        return dict(self._variable_list_fn())

    def clear(self) -> None:
        self._series.clear()
        self._curves.clear()
        self._plot.clear()
        self._legend = self._plot.addLegend()
        self._sample_index = 0
        self._start_time = None
        self._time_axis.set_start_time(None)
        self._update_axis_labels()

    def _resize_buffers(self, new_size: int) -> None:
        if new_size <= 0:
            return
        self._buffer_size = new_size
        resized: dict[str, deque[tuple[float, float]]] = {}
        for name, data in self._series.items():
            resized[name] = deque(data, maxlen=new_size)
        self._series = resized

    # -- new values-based entry point -----------------------------------------

    def handle_values(self, values: dict[str, float], updated_names: set[str] | None = None) -> None:
        """Accept a pre-parsed values dict from the VariableManager.

        *values* maps variable names to their current numeric value.
        *updated_names*, when given, restricts which variables are
        actually plotted (only those that changed since the last call).
        """
        if not self._enabled:
            return
        if not values:
            return

        if self._config.mode == "xy":
            self._handle_xy(values, updated_names)
        else:
            self._handle_timeseries(values, updated_names)

    def _handle_timeseries(
        self,
        values: dict[str, float],
        updated_names: set[str] | None = None,
    ) -> None:
        series_points: list[tuple[str, float]] = []
        for var in self._config.series_variables:
            if var not in values:
                continue
            if updated_names is not None and var not in updated_names:
                continue
            series_points.append((var, float(values[var])))

        if not series_points:
            return

        x_value = datetime.now().timestamp()
        if self._start_time is None:
            self._start_time = x_value
            self._time_axis.set_start_time(self._start_time)
        for name, y_value in series_points:
            self._append_point(name, x_value, y_value)

    def _handle_xy(
        self,
        values: dict[str, float],
        updated_names: set[str] | None = None,
    ) -> None:
        x_key = self._config.xy_x_var
        y_key = self._config.xy_y_var
        if x_key not in values or y_key not in values:
            return
        if updated_names is not None and x_key not in updated_names and y_key not in updated_names:
            return
        x_value = float(values[x_key])
        y_value = float(values[y_key])
        self._append_point(y_key, x_value, y_value)

    def _append_point(self, name: str, x_value: float, y_value: float) -> None:
        if name not in self._series:
            self._series[name] = deque(maxlen=self._config.buffer_size)
        self._series[name].append((x_value, y_value))

    def _refresh_plot(self) -> None:
        if not self._enabled:
            return
        if self._config.mode == "timeseries":
            selected_labels = set(self._config.series_variables)
        else:
            selected_labels = {self._config.xy_y_var}
        for name, points in self._series.items():
            if name not in selected_labels:
                continue
            color = self._curve_colors[len(self._curves) % len(self._curve_colors)]
            labels = self._name_to_label()
            display_name = labels.get(name, name)
            if name not in self._curves:
                if self._config.mode == "xy":
                    self._curves[name] = self._plot.plot(
                        pen=None,
                        symbol="o",
                        symbolSize=5,
                        symbolBrush=pg.mkBrush(color),
                        symbolPen=pg.mkPen(color=color),
                        name=display_name,
                    )
                else:
                    self._curves[name] = self._plot.plot(
                        pen=pg.mkPen(color=color, width=2),
                        name=display_name,
                    )
            x_values = [p[0] for p in points]
            y_values = [p[1] for p in points]
            if self._config.mode == "xy":
                self._curves[name].setData(
                    x_values,
                    y_values,
                    pen=None,
                    symbol="o",
                    symbolSize=5,
                    symbolBrush=pg.mkBrush(color),
                    symbolPen=pg.mkPen(color=color),
                    name=display_name,
                )
            else:
                self._curves[name].setData(x_values, y_values, name=display_name)

    def _reset_plot(self) -> None:
        self.clear()
        self._update_axis_labels()

    def _migrate_series_labels(self, old_config: PlotConfig, new_config: PlotConfig) -> None:
        """Rekey series/curves when variable selection changes."""
        old_vars = set(old_config.series_variables)
        new_vars = set(new_config.series_variables)
        # Nothing to migrate -- names are used directly now
        _ = old_vars, new_vars

    def _prune_removed_series(self) -> None:
        """Remove series and curves that are no longer in the current config selection."""
        if self._config.mode == "timeseries":
            selected = set(self._config.series_variables)
        else:
            selected = {self._config.xy_y_var}
        for name in list(self._series.keys()):
            if name not in selected:
                del self._series[name]
                if name in self._curves:
                    self._plot.removeItem(self._curves[name])
                    del self._curves[name]
        self._refresh_plot()

    def _update_axis_labels(self) -> None:
        labels = self._name_to_label()
        if self._config.mode == "xy":
            x_label = labels.get(self._config.xy_x_var, self._config.xy_x_var) if self._config.xy_x_var else "X"
            y_label = labels.get(self._config.xy_y_var, self._config.xy_y_var) if self._config.xy_y_var else "Y"
            self._plot.setLabel("bottom", x_label)
            self._plot.setLabel("left", y_label)
        else:
            self._plot.setLabel("bottom", "timestamp")
            self._plot.setLabel("left", "Value")

    def current_point_count(self) -> int:
        if not self._series:
            return 0
        return max(len(points) for points in self._series.values())


class TimeAxis(pg.AxisItem):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._start_time: float | None = None
        self._mode = "timeseries"

    def set_start_time(self, start_time: float | None) -> None:
        self._start_time = start_time

    def set_mode(self, mode: str) -> None:
        self._mode = mode

    def tickStrings(self, values, scale, spacing):
        if self._mode != "timeseries":
            return super().tickStrings(values, scale, spacing)
        strings = []
        for value in values:
            if self._start_time is None:
                strings.append("")
                continue
            try:
                dt = datetime.fromtimestamp(value)
                strings.append(dt.strftime("%H:%M:%S"))
            except (OSError, OverflowError, ValueError):
                strings.append(f"{value - self._start_time:.1f}s")
        return strings
