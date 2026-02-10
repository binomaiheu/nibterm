from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMdiArea,
    QMdiSubWindow,
    QDialog,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .plot_panel import PlotConfig, PlotPanel
from .plot_setup_dialog import PlotSetupDialog


class DashboardWindow(QWidget):
    closed = Signal()

    def __init__(self, settings: QSettings, config: PlotConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("nibterm - Dashboard")
        self.setMinimumSize(800, 500)
        self._settings = settings
        self._config = config
        self._mdi = QMdiArea(self)
        self._mdi.setViewMode(QMdiArea.ViewMode.SubWindowView)

        self._toolbar = QToolBar("Dashboard")
        self._toolbar.setMovable(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self._mdi)

        self._plot_panels: list[PlotPanel] = []
        self._plot_configs: dict[PlotPanel, PlotConfig] = {}
        self._plot_windows: dict[PlotPanel, QMdiSubWindow] = {}
        self._inactive_plots: set[PlotPanel] = set()
        self._restored = False

    def add_plot(self) -> None:
        plot = PlotPanel()
        config = self._new_plot_config()
        plot.set_config(config)
        plot.set_enabled(False)
        sub = QMdiSubWindow()
        sub.setWidget(plot)
        sub.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        sub.destroyed.connect(lambda _=None, p=plot: self._unregister_plot(p))
        self._mdi.addSubWindow(sub)
        sub.show()
        self._plot_panels.append(plot)
        self._plot_configs[plot] = config
        self._plot_windows[plot] = sub
        self._inactive_plots.add(plot)
        sub.setWindowTitle("Plot (inactive)")
        self._mdi.setActiveSubWindow(sub)
        self._mdi.tileSubWindows()

    def remove_plot(self) -> None:
        active = self._mdi.activeSubWindow()
        if not active:
            return
        widget = active.widget()
        if isinstance(widget, PlotPanel):
            self._unregister_plot(widget)
        active.close()
        self._mdi.tileSubWindows()

    def apply_config(self, config: PlotConfig) -> None:
        self._config = config
        for plot in self._plot_panels:
            plot_config = self._plot_configs.get(plot)
            if not plot_config:
                continue
            plot_config.delimiter = config.delimiter
            plot_config.column_names = config.column_names
            plot_config.transform_expressions = config.transform_expressions
            plot.set_config(plot_config)
            self._update_plot_title(plot, plot_config)
        self._refresh_variable_lists()

    def _refresh_variable_lists(self) -> None:
        variables = self._config_variables()
        self._cached_variables = variables

    def _config_variables(self) -> list[tuple[str, str]]:
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

    def _current_plot(self) -> tuple[PlotPanel | None, PlotConfig | None]:
        active = self._mdi.activeSubWindow()
        if not active:
            return None, None
        widget = active.widget()
        if not isinstance(widget, PlotPanel):
            return None, None
        return widget, self._plot_configs.get(widget)

    def _new_plot_config(self) -> PlotConfig:
        config = deepcopy(self._config)
        if not config.series_variables:
            config.series_variables = [f"c{idx}" for idx in config.columns]
        if not config.xy_x_var:
            config.xy_x_var = "c0"
        if not config.xy_y_var:
            config.xy_y_var = "c1"
        return config

    def _open_setup(self) -> None:
        plot, config = self._current_plot()
        if not plot or not config:
            return
        dialog = PlotSetupDialog(self._config_variables(), self)
        dialog.load(config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated = dialog.config()
            config.mode = updated.mode
            config.series_variables = updated.series_variables
            config.xy_x_var = updated.xy_x_var
            config.xy_y_var = updated.xy_y_var
            config.buffer_size = updated.buffer_size
            config.update_ms = updated.update_ms
            plot.update_config(config)
            plot.set_enabled(True)
            self._inactive_plots.discard(plot)
            self._update_plot_title(plot, config)

    def handle_line(self, line: str) -> None:
        for plot in self._plot_panels:
            plot.handle_line(line)

    def clear_plots(self) -> None:
        for plot in self._plot_panels:
            plot.clear()

    def has_active_plot(self) -> bool:
        plot, _ = self._current_plot()
        return plot is not None

    def clear_active_plot(self) -> None:
        plot, _ = self._current_plot()
        if plot:
            plot.clear()

    def setup_active_plot(self) -> None:
        self._open_setup()

    def tile_plots(self) -> None:
        self._mdi.tileSubWindows()

    def cascade_plots(self) -> None:
        self._mdi.cascadeSubWindows()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
        self.closed.emit()

    def save_state(self) -> None:
        self._settings.setValue("dashboard/plot_count", len(self._plot_panels))
        for idx, plot in enumerate(self._plot_panels):
            config = self._plot_configs.get(plot)
            if not config:
                continue
            prefix = f"dashboard/plots/{idx}"
            self._settings.setValue(f"{prefix}/mode", config.mode)
            self._settings.setValue(
                f"{prefix}/series_vars",
                ";".join(config.series_variables),
            )
            self._settings.setValue(f"{prefix}/xy_x_var", config.xy_x_var)
            self._settings.setValue(f"{prefix}/xy_y_var", config.xy_y_var)
            self._settings.setValue(f"{prefix}/buffer_size", config.buffer_size)
            self._settings.setValue(f"{prefix}/update_ms", config.update_ms)
            self._settings.setValue(f"{prefix}/inactive", plot in self._inactive_plots)

    def restore_state(self) -> None:
        if self._restored:
            return
        self._restored = True
        self._clear_all_plots()
        count = self._settings.value("dashboard/plot_count", 0, int)
        if count <= 0:
            self.add_plot()
            return
        for _ in range(count):
            self.add_plot()
        for idx, plot in enumerate(self._plot_panels):
            prefix = f"dashboard/plots/{idx}"
            config = self._plot_configs.get(plot)
            if not config:
                continue
            config.mode = self._settings.value(f"{prefix}/mode", config.mode, str)
            series_vars = self._settings.value(f"{prefix}/series_vars", "", str)
            if series_vars:
                config.series_variables = [v for v in series_vars.split(";") if v]
            config.xy_x_var = self._settings.value(f"{prefix}/xy_x_var", config.xy_x_var, str)
            config.xy_y_var = self._settings.value(f"{prefix}/xy_y_var", config.xy_y_var, str)
            config.buffer_size = self._settings.value(f"{prefix}/buffer_size", config.buffer_size, int)
            config.update_ms = self._settings.value(f"{prefix}/update_ms", config.update_ms, int)
            plot.update_config(config)
            inactive = self._settings.value(f"{prefix}/inactive", False, bool)
            if inactive:
                plot.set_enabled(False)
                self._inactive_plots.add(plot)
            else:
                plot.set_enabled(True)
                self._inactive_plots.discard(plot)
            self._update_plot_title(plot, config)

    def _clear_all_plots(self) -> None:
        for sub in self._mdi.subWindowList():
            sub.close()
        self._plot_panels.clear()
        self._plot_configs.clear()
        self._plot_windows.clear()
        self._inactive_plots.clear()

    def _unregister_plot(self, plot: PlotPanel) -> None:
        if plot in self._plot_panels:
            self._plot_panels = [p for p in self._plot_panels if p is not plot]
        self._plot_configs.pop(plot, None)
        self._plot_windows.pop(plot, None)
        self._inactive_plots.discard(plot)

    def _plot_title(self, config: PlotConfig) -> str:
        if config.mode == "xy":
            x_label = self._variable_label(config.xy_x_var, config)
            y_label = self._variable_label(config.xy_y_var, config)
            return f"XY: {x_label} vs {y_label} (buffer: {config.buffer_size})"
        labels = [self._variable_label(key, config) for key in config.series_variables]
        if not labels:
            return f"Timeseries (buffer: {config.buffer_size})"
        return f"Timeseries: {', '.join(labels)} (buffer: {config.buffer_size})"

    def _variable_label(self, key: str, config: PlotConfig) -> str:
        if key.startswith("c") and key[1:].isdigit():
            idx = int(key[1:])
            return config.column_names.get(idx, key)
        return key

    def _update_plot_title(self, plot: PlotPanel, config: PlotConfig) -> None:
        window = self._plot_windows.get(plot)
        if window:
            if plot in self._inactive_plots:
                window.setWindowTitle("Plot (inactive)")
            else:
                window.setWindowTitle(self._plot_title(config))
