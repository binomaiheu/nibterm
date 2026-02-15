from __future__ import annotations

from copy import deepcopy
from typing import Callable

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QMdiArea,
    QMdiSubWindow,
    QDialog,
    QVBoxLayout,
    QWidget,
)

from ..config import settings_keys as SK
from ..config.plot_config import PlotConfig
from .plot_panel import PlotPanel
from .plot_setup_dialog import PlotSetupDialog


class DashboardWindow(QWidget):
    closed = Signal()

    def __init__(
        self,
        settings: QSettings,
        config: PlotConfig,
        variable_list_fn: Callable[[], list[tuple[str, str]]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("nibterm - Dashboard")
        self.setMinimumSize(800, 500)
        self._settings = settings
        self._config = config
        self._variable_list_fn = variable_list_fn
        self._mdi = QMdiArea(self)
        self._mdi.setViewMode(QMdiArea.ViewMode.SubWindowView)

        layout = QVBoxLayout(self)
        layout.addWidget(self._mdi)

        self._plot_panels: list[PlotPanel] = []
        self._plot_configs: dict[PlotPanel, PlotConfig] = {}
        self._plot_windows: dict[PlotPanel, QMdiSubWindow] = {}
        self._inactive_plots: set[PlotPanel] = set()
        self._restored = False

    def add_plot(self) -> None:
        plot = PlotPanel()
        plot.set_variable_list_fn(self._variable_list_fn)
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

    def on_variables_changed(self) -> None:
        """Called when the global variable list changes.

        Updates plot titles to reflect any renamed variables.
        """
        for plot in self._plot_panels:
            config = self._plot_configs.get(plot)
            if config:
                self._update_plot_title(plot, config)

    def _current_plot(self) -> tuple[PlotPanel | None, PlotConfig | None]:
        active = self._mdi.activeSubWindow()
        if not active:
            return None, None
        widget = active.widget()
        if not isinstance(widget, PlotPanel):
            return None, None
        return widget, self._plot_configs.get(widget)

    def _new_plot_config(self) -> PlotConfig:
        return deepcopy(self._config)

    def _open_setup(self) -> None:
        plot, config = self._current_plot()
        if not plot or not config:
            return
        variables = self._variable_list_fn()
        dialog = PlotSetupDialog(variables, self)
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

    def handle_values(self, values: dict[str, float], updated_names: set[str] | None = None) -> None:
        """Push a values dict (from VariableManager) to all plot panels."""
        for plot in self._plot_panels:
            plot.handle_values(values, updated_names=updated_names)
            config = self._plot_configs.get(plot)
            if config:
                self._update_plot_title(plot, config)

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

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        self.hide()
        self.closed.emit()

    def save_state(self) -> None:
        self._settings.setValue(SK.DASHBOARD_PLOT_COUNT, len(self._plot_panels))
        for idx, plot in enumerate(self._plot_panels):
            config = self._plot_configs.get(plot)
            if not config:
                continue
            prefix = SK.DASHBOARD_PLOTS_PREFIX.format(idx)
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
        count = self._settings.value(SK.DASHBOARD_PLOT_COUNT, 0, int)
        if count <= 0:
            self.add_plot()
            return
        for _ in range(count):
            self.add_plot()
        for idx, plot in enumerate(self._plot_panels):
            prefix = SK.DASHBOARD_PLOTS_PREFIX.format(idx)
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

    def _plot_title(self, plot: PlotPanel, config: PlotConfig) -> str:
        count = plot.current_point_count()
        if config.mode == "xy":
            return (
                f"XY: {config.xy_x_var} vs {config.xy_y_var} "
                f"(buffer: {count}/{config.buffer_size})"
            )
        labels = config.series_variables
        if not labels:
            return f"Timeseries (buffer: {count}/{config.buffer_size})"
        return (
            f"Timeseries: {', '.join(labels)} "
            f"(buffer: {count}/{config.buffer_size})"
        )

    def _update_plot_title(self, plot: PlotPanel, config: PlotConfig) -> None:
        window = self._plot_windows.get(plot)
        if window:
            if plot in self._inactive_plots:
                window.setWindowTitle("Plot (inactive)")
            else:
                window.setWindowTitle(self._plot_title(plot, config))
