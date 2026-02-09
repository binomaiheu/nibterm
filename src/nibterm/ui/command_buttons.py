from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from ..config.commands_schema import CommandPreset, load_preset


class CommandButtons(QWidget):
    command_requested = Signal(str)
    preset_loaded = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._preset: CommandPreset | None = None

        self._header_label = QLabel("No preset loaded")
        self._load_button = QPushButton("Load preset...")
        self._clear_button = QPushButton("Clear")
        self._load_button.clicked.connect(self._load_preset)
        self._clear_button.clicked.connect(self.clear)

        header_row = QHBoxLayout()
        header_row.addWidget(self._header_label, stretch=1)
        header_row.addWidget(self._load_button)
        header_row.addWidget(self._clear_button)

        self._buttons_widget = QWidget()
        self._buttons_layout = QGridLayout(self._buttons_widget)
        self._buttons_layout.setContentsMargins(0, 0, 0, 0)
        self._buttons_layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._buttons_widget)

        box = QGroupBox("Commands")
        box_layout = QVBoxLayout(box)
        box_layout.addLayout(header_row)
        box_layout.addWidget(scroll)

        layout = QVBoxLayout(self)
        layout.addWidget(box)

    def set_preset(self, preset: CommandPreset) -> None:
        self._preset = preset
        self._header_label.setText(preset.name)
        self._rebuild_buttons()

    def clear(self) -> None:
        self._preset = None
        self._header_label.setText("No preset loaded")
        self._rebuild_buttons()

    def _rebuild_buttons(self) -> None:
        while self._buttons_layout.count():
            item = self._buttons_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self._preset:
            return

        columns = 3
        for idx, command in enumerate(self._preset.commands):
            button = QPushButton(command.label)
            button.clicked.connect(
                lambda _checked=False, cmd=command.command: self.command_requested.emit(cmd)
            )
            row = idx // columns
            col = idx % columns
            self._buttons_layout.addWidget(button, row, col)

    def _load_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load command preset",
            "",
            "YAML files (*.yaml *.yml)",
        )
        if not path:
            return
        self.load_preset_from_path(path)

    def load_preset_from_path(self, path: str | Path) -> None:
        try:
            preset = load_preset(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Preset error", str(exc))
            return
        self.set_preset(preset)
        self.preset_loaded.emit(str(path))
