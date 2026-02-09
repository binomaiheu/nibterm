from __future__ import annotations

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import QMainWindow

from .plot_panel import PlotPanel


class PlotWindow(QMainWindow):
    window_closed = Signal()

    def __init__(self, plot_panel: PlotPanel, settings: QSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("nibterm - Plot")
        self._plot_panel = plot_panel
        self._settings = settings
        self.setCentralWidget(self._plot_panel)

    def save_state(self) -> None:
        self._settings.setValue("plot_window/geometry", self.saveGeometry())

    def restore_state(self) -> None:
        geometry = self._settings.value("plot_window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
        self.window_closed.emit()
