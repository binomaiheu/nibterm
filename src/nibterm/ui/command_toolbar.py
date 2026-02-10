from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QToolBar, QMessageBox

from ..config.commands_schema import CommandPreset, load_preset


class CommandToolbar(QToolBar):
    command_requested = Signal(str)
    preset_loaded = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("Commands", parent)
        self.setOrientation(Qt.Orientation.Vertical)
        self.setMovable(False)

        self._preset: CommandPreset | None = None
        self._command_actions: list[QAction] = []

    def set_preset(self, preset: CommandPreset) -> None:
        self._preset = preset
        self._rebuild_actions()

    def clear_preset(self) -> None:
        self._preset = None
        self._rebuild_actions()

    def load_preset_from_path(self, path: str | Path) -> None:
        try:
            preset = load_preset(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Preset error", str(exc))
            return
        self.set_preset(preset)
        self.preset_loaded.emit(str(path))

    def load_preset_via_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load command preset",
            "",
            "YAML files (*.yaml *.yml)",
        )
        if not path:
            return
        self.load_preset_from_path(path)

    def _rebuild_actions(self) -> None:
        for action in self._command_actions:
            self.removeAction(action)
        self._command_actions.clear()

        if not self._preset:
            return

        for command in self._preset.commands:
            action = QAction(command.label, self)
            action.triggered.connect(
                lambda _checked=False, cmd=command.command: self.command_requested.emit(cmd)
            )
            self.addAction(action)
            self._command_actions.append(action)
