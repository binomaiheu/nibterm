from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import ast
from datetime import datetime
import math
import re

import pyqtgraph as pg
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..config import defaults


@dataclass
class TransformExpression:
    name: str
    expr: str


def _parse_int_set(text: str) -> set[int]:
    result: set[int] = set()
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            continue
    return result


def _serialize_int_set(s: set[int]) -> str:
    return ";".join(str(i) for i in sorted(s))


@dataclass
class PlotConfig:
    delimiter: str = defaults.DEFAULT_PLOT_DELIMITER
    mode: str = "timeseries"
    columns: list[int] = field(default_factory=lambda: [0])
    x_column: int = 0
    y_column: int = 1
    column_names: dict[int, str] = field(default_factory=dict)
    mqtt_column_indices: set[int] = field(default_factory=set)
    transform_expressions: list[TransformExpression] = field(default_factory=list)
    series_variables: list[str] = field(default_factory=list)
    xy_x_var: str = "c0"
    xy_y_var: str = "c1"
    buffer_size: int = defaults.DEFAULT_PLOT_BUFFER_SIZE
    update_ms: int = defaults.DEFAULT_PLOT_UPDATE_MS

    def to_qsettings(self, settings: QSettings) -> None:
        settings.setValue("plot/delimiter", self.delimiter)
        settings.setValue("plot/mode", self.mode)
        settings.setValue("plot/columns", _serialize_int_list(self.columns))
        settings.setValue("plot/x_column", self.x_column)
        settings.setValue("plot/y_column", self.y_column)
        settings.setValue(
            "plot/column_names",
            _serialize_column_names(self.column_names),
        )
        settings.setValue(
            "plot/mqtt_column_indices",
            _serialize_int_set(self.mqtt_column_indices),
        )
        settings.setValue(
            "plot/transform",
            _serialize_transform(self.transform_expressions),
        )
        settings.setValue(
            "plot/series_vars",
            _serialize_string_list(self.series_variables),
        )
        settings.setValue("plot/xy_x_var", self.xy_x_var)
        settings.setValue("plot/xy_y_var", self.xy_y_var)
        settings.setValue("plot/buffer_size", self.buffer_size)
        settings.setValue("plot/update_ms", self.update_ms)

    @staticmethod
    def from_qsettings(settings: QSettings) -> "PlotConfig":
        columns = _parse_int_list(settings.value("plot/columns", "0", str), [0])
        names = _parse_column_names(settings.value("plot/column_names", "", str))
        mqtt_indices = _parse_int_set(
            settings.value("plot/mqtt_column_indices", "", str)
        )
        transforms = _parse_transform_string(
            settings.value("plot/transform", "", str)
        )
        series_vars = _parse_string_list(
            settings.value("plot/series_vars", "", str)
        )
        xy_x_var = settings.value("plot/xy_x_var", "", str)
        xy_y_var = settings.value("plot/xy_y_var", "", str)
        if not series_vars:
            series_vars = [f"c{idx}" for idx in columns]
        if not xy_x_var:
            xy_x_var = f"c{settings.value('plot/x_column', 0, int)}"
        if not xy_y_var:
            xy_y_var = f"c{settings.value('plot/y_column', 1, int)}"
        return PlotConfig(
            delimiter=settings.value(
                "plot/delimiter",
                defaults.DEFAULT_PLOT_DELIMITER,
                str,
            ),
            mode=settings.value("plot/mode", "timeseries", str),
            columns=columns,
            x_column=settings.value("plot/x_column", 0, int),
            y_column=settings.value("plot/y_column", 1, int),
            column_names=names,
            mqtt_column_indices=mqtt_indices,
            transform_expressions=transforms,
            series_variables=series_vars,
            xy_x_var=xy_x_var,
            xy_y_var=xy_y_var,
            buffer_size=settings.value(
                "plot/buffer_size",
                defaults.DEFAULT_PLOT_BUFFER_SIZE,
                int,
            ),
            update_ms=settings.value(
                "plot/update_ms",
                defaults.DEFAULT_PLOT_UPDATE_MS,
                int,
            ),
        )


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

    def available_variables(self) -> list[tuple[str, str]]:
        names = self._config.column_names
        variables: list[tuple[str, str]] = []
        max_index = max(names.keys(), default=-1)
        max_index = max(max_index, 0)
        for idx in range(max_index + 1):
            key = f"c{idx}"
            label = names.get(idx, key)
            display = f"{label} ({key})" if label != key else label
            variables.append((key, display))
        for transform in self._config.transform_expressions:
            variables.append((transform.name, f"{transform.name} (fx)"))
        return variables

    def set_config(self, config: PlotConfig) -> None:
        self._config = config
        self._timer.setInterval(config.update_ms)
        self._time_axis.set_mode(config.mode)
        self._reset_plot()

    def update_config(self, config: PlotConfig) -> None:
        if self._buffer_size != config.buffer_size:
            self._resize_buffers(config.buffer_size)
            self._refresh_plot()
        if self._config.delimiter != config.delimiter or self._config.transform_expressions != config.transform_expressions:
            self._config = config
            self._timer.setInterval(config.update_ms)
            self._time_axis.set_mode(config.mode)
            self._reset_plot()
            return
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

    def handle_line(self, line: str, updated_names: set[str] | None = None) -> None:
        if not self._enabled:
            return
        tokens = [t.strip() for t in line.split(self._config.delimiter)]
        if not tokens:
            return
        values: list[float | None] = []
        for token in tokens:
            try:
                values.append(float(token))
            except ValueError:
                values.append(None)
        if all(value is None for value in values):
            return

        variables, display_names = _build_variable_maps(values, self._config.column_names)
        transform_values = _evaluate_transforms(
            self._config.transform_expressions,
            variables,
        )
        for name, value in transform_values:
            variables[name] = value
            display_names[name] = name

        if self._config.mode == "xy":
            self._handle_xy(variables, display_names, updated_names)
        else:
            self._handle_timeseries(variables, display_names, updated_names)

    def _handle_timeseries(
        self,
        variables: dict[str, float],
        display_names: dict[str, str],
        updated_names: set[str] | None = None,
    ) -> None:
        series_points: list[tuple[str, float]] = []
        for var in self._config.series_variables:
            if var not in variables:
                continue
            if updated_names is not None and var not in updated_names:
                continue
            label = display_names.get(var, var)
            series_points.append((label, float(variables[var])))

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
        variables: dict[str, float],
        display_names: dict[str, str],
        updated_names: set[str] | None = None,
    ) -> None:
        x_key = self._config.xy_x_var
        y_key = self._config.xy_y_var
        if x_key not in variables or y_key not in variables:
            return
        if updated_names is not None and x_key not in updated_names and y_key not in updated_names:
            return
        x_value = float(variables[x_key])
        series_points = [(display_names.get(y_key, y_key), float(variables[y_key]))]

        for name, y_value in series_points:
            self._append_point(name, x_value, y_value)

    def _append_point(self, name: str, x_value: float, y_value: float) -> None:
        if name not in self._series:
            self._series[name] = deque(maxlen=self._config.buffer_size)
        self._series[name].append((x_value, y_value))

    def _refresh_plot(self) -> None:
        if not self._enabled:
            return
        if self._config.mode == "timeseries":
            selected_labels = {
                self._variable_label(key) for key in self._config.series_variables
            }
        else:
            selected_labels = {self._variable_label(self._config.xy_y_var)}
        for name, points in self._series.items():
            if name not in selected_labels:
                continue
            color = self._curve_colors[len(self._curves) % len(self._curve_colors)]
            if name not in self._curves:
                if self._config.mode == "xy":
                    self._curves[name] = self._plot.plot(
                        pen=None,
                        symbol="o",
                        symbolSize=5,
                        symbolBrush=pg.mkBrush(color),
                        symbolPen=pg.mkPen(color=color),
                        name=name,
                    )
                else:
                    self._curves[name] = self._plot.plot(
                        pen=pg.mkPen(color=color, width=2),
                        name=name,
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
                )
            else:
                self._curves[name].setData(x_values, y_values)

    def _reset_plot(self) -> None:
        self.clear()
        self._update_axis_labels()

    def _migrate_series_labels(self, old_config: PlotConfig, new_config: PlotConfig) -> None:
        """When column names change (e.g. MQTT variable renamed), rekey series/curves so data and plot keep the new name."""
        all_indices = set(old_config.column_names.keys()) | set(new_config.column_names.keys())
        for idx in all_indices:
            old_label = old_config.column_names.get(idx, f"c{idx}")
            new_label = new_config.column_names.get(idx, f"c{idx}")
            if old_label == new_label or old_label not in self._series:
                continue
            self._series[new_label] = self._series.pop(old_label)
            if old_label in self._curves:
                curve = self._curves.pop(old_label)
                if hasattr(curve, "opts") and isinstance(getattr(curve, "opts", None), dict):
                    curve.opts["name"] = new_label
                self._curves[new_label] = curve

    def _prune_removed_series(self) -> None:
        """Remove series and curves that are no longer in the current config selection."""
        if self._config.mode == "timeseries":
            selected_labels = {
                self._variable_label(key) for key in self._config.series_variables
            }
        else:
            selected_labels = {self._variable_label(self._config.xy_y_var)}
        for name in list(self._series.keys()):
            if name not in selected_labels:
                del self._series[name]
                if name in self._curves:
                    self._plot.removeItem(self._curves[name])
                    del self._curves[name]
        self._refresh_plot()

    def _update_axis_labels(self) -> None:
        if self._config.mode == "xy":
            x_label = self._variable_label(self._config.xy_x_var)
            self._plot.setLabel("bottom", x_label)
            y_label = self._variable_label(self._config.xy_y_var)
            self._plot.setLabel("left", y_label)
        else:
            self._plot.setLabel("bottom", "timestamp")
            self._plot.setLabel("left", "Value")

    def current_point_count(self) -> int:
        if not self._series:
            return 0
        return max(len(points) for points in self._series.values())

    def _variable_label(self, key: str) -> str:
        if key.startswith("c") and key[1:].isdigit():
            index = int(key[1:])
            return self._config.column_names.get(index, key)
        return key


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


def _serialize_int_list(values: list[int]) -> str:
    return ",".join(str(v) for v in values)


def _parse_column_names(text: str) -> dict[int, str]:
    names: dict[int, str] = {}
    for entry in text.split(";"):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        idx_text, name = entry.split("=", 1)
        try:
            idx = int(idx_text.strip())
        except ValueError:
            continue
        name = name.strip()
        if name:
            names[idx] = name
    return names


def _serialize_column_names(names: dict[int, str]) -> str:
    parts: list[str] = []
    for idx in sorted(names.keys()):
        parts.append(f"{idx}={names[idx]}")
    return "; ".join(parts)


def _serialize_string_list(values: list[str]) -> str:
    return "; ".join(value for value in values if value)


def _parse_string_list(text: str) -> list[str]:
    values: list[str] = []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if chunk:
            values.append(chunk)
    return values

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


def _build_variable_maps(
    values: list[float | None],
    column_names: dict[int, str],
) -> tuple[dict[str, float], dict[str, str]]:
    variables: dict[str, float] = {}
    display_names: dict[str, str] = {}
    for idx, value in enumerate(values):
        if value is None:
            continue
        key = f"c{idx}"
        variables[key] = float(value)
        display_names[key] = column_names.get(idx, key)
        if idx in column_names:
            name = column_names[idx]
            ident = _sanitize_identifier(name)
            if ident:
                variables[ident] = float(value)
    return variables, display_names


def _sanitize_identifier(name: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "_", name.strip())
    if not cleaned:
        return ""
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


_ALLOWED_FUNCS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "min": min,
    "max": max,
}


def _evaluate_transforms(
    transforms: list[TransformExpression],
    variables: dict[str, float],
) -> list[tuple[str, float]]:
    results: list[tuple[str, float]] = []
    for transform in transforms:
        try:
            value = _safe_eval(transform.expr, variables)
        except Exception:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        results.append((transform.name, numeric))
    return results


def _safe_eval(expr: str, variables: dict[str, float]) -> float:
    tree = ast.parse(expr, mode="eval")
    _validate_ast(tree)
    scope = {"__builtins__": {}}
    scope.update(_ALLOWED_FUNCS)
    scope.update({"pi": math.pi, "e": math.e})
    scope.update(variables)
    return eval(compile(tree, "<expr>", "eval"), scope, {})


def _validate_ast(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Load)):
            continue
        if isinstance(node, ast.Constant):
            continue
        if isinstance(node, ast.BinOp) and isinstance(
            node.op,
            (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod),
        ):
            continue
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            continue
        if isinstance(node, ast.Name):
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id not in _ALLOWED_FUNCS:
                raise ValueError("Unsupported function in expression.")
            continue
        raise ValueError("Unsupported expression.")


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
            except Exception:
                strings.append(f"{value - self._start_time:.1f}s")
        return strings
