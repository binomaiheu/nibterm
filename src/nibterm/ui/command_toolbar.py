from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal, QSize
from PySide6.QtGui import QAction, QFontMetrics
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from ..config.commands_schema import CommandPreset, load_preset


class CommandToolbar(QToolBar):
    command_requested = Signal(str)
    preset_loaded = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("Commands", parent)
        self.setOrientation(Qt.Orientation.Vertical)
        self.setMovable(False)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        self._settings = QSettings()
        self._preset: CommandPreset | None = None
        self._command_actions: list[QAction] = []
        self._param_inputs: dict[str, dict[str, QLineEdit]] = {}
        self._param_summaries: dict[str, QLabel] = {}
        self._param_containers: dict[str, QWidget] = {}

        self._profile_label = QLabel("-")
        self._profile_label.setStyleSheet("font-weight: bold;")
        profile_widget = QWidget()
        profile_layout = QHBoxLayout(profile_widget)
        profile_layout.setContentsMargins(6, 4, 6, 4)
        profile_layout.addWidget(self._profile_label)
        profile_layout.addStretch(1)
        self.addWidget(profile_widget)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(2)
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setRootIsDecorated(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self._tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectItems)
        self._tree.setAlternatingRowColors(False)
        self._tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._tree.setStyleSheet(
            "QTreeView::item:selected { background: transparent; color: palette(text); }"
            "QTreeView::item:focus { outline: none; }"
            "QTreeView::item:selected:active { background: transparent; }"
            "QTreeView::item:selected:!active { background: transparent; }"
            "QTreeView { selection-background-color: transparent; alternate-background-color: transparent; }"
            "QTreeView::item:hover { background: transparent; }"
            "QTreeView::item { background: transparent; }"
            "QToolButton:focus { outline: none; background: transparent; }"
        )
        self.addWidget(self._tree)

    def set_preset(self, preset: CommandPreset) -> None:
        self._preset = preset
        self._profile_label.setText(preset.name)
        self._rebuild_actions()

    def clear_preset(self) -> None:
        self._preset = None
        self._profile_label.setText("-")
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
        self._command_actions.clear()
        self._param_inputs.clear()
        self._param_summaries.clear()
        self._tree.clear()

        if not self._preset:
            return

        for command in self._preset.commands:
            action = QAction(command.label, self)
            if command.color:
                action.setData({"color": command.color})
            action.triggered.connect(
                lambda _checked=False, cmd=command.command, label=command.label: self._emit_command(cmd, label)
            )
            self._command_actions.append(action)
            self._add_command_item(action, command)
        self._update_button_sizes()

    def _update_button_sizes(self) -> None:
        if not self._command_actions:
            return
        fm = QFontMetrics(self.font())
        max_width = max(fm.horizontalAdvance(action.text()) for action in self._command_actions)
        padded = max_width + 24
        for button in self.findChildren(QToolButton):
            action = button.defaultAction()
            if action in self._command_actions:
                if isinstance(action.data(), dict):
                    color = action.data().get("color")
                    if color:
                        button.setStyleSheet(f"background-color: {color};")
                button.setFixedWidth(padded)

    def _add_command_item(self, action: QAction, command) -> None:
        item = QTreeWidgetItem(self._tree)
        item.setFirstColumnSpanned(True)
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        button = QToolButton()
        button.setDefaultAction(action)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        button.setMinimumHeight(26)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        if command.description:
            button.setToolTip(command.description)
        header_layout.addWidget(button)
        summary = QLabel("")
        summary.setStyleSheet("color: #666;")
        header_layout.addWidget(summary)
        header_layout.addStretch(1)
        self._param_summaries[command.label] = summary
        self._tree.setItemWidget(item, 0, header_widget)
        item.setSizeHint(0, QSize(0, 34))

        if command.params:
            param_inputs: dict[str, QLineEdit] = {}
            for param in command.params:
                child = QTreeWidgetItem(item)
                label = param.label or param.name
                child.setText(0, label)
                if param.description:
                    child.setToolTip(0, param.description)
                child.setSizeHint(0, QSize(0, 28))
                entry = QLineEdit()
                key = self._param_key(command.label, param.name)
                stored = self._settings.value(key, "", str)
                if stored:
                    entry.setText(stored)
                elif param.default:
                    entry.setText(param.default)
                entry.textChanged.connect(
                    lambda value, k=key: self._settings.setValue(k, value)
                )
                entry.textChanged.connect(
                    lambda _value, label=command.label: self._update_param_summary(label)
                )
                param_inputs[param.name] = entry
                self._tree.setItemWidget(child, 1, entry)
            self._param_inputs[command.label] = param_inputs
            self._update_param_summary(command.label)
        else:
            summary.setText("(n/a)")

    def _param_key(self, label: str, param_name: str) -> str:
        preset = self._preset.name if self._preset else "unknown"
        return f"commands/params/{preset}/{label}/{param_name}"

    def _emit_command(self, template: str, label: str) -> None:
        params = {}
        missing: list[str] = []
        inputs = self._param_inputs.get(label, {})
        for name, entry in inputs.items():
            value = entry.text().strip()
            if not value:
                missing.append(name)
            params[name] = value
        if missing:
            QMessageBox.warning(
                self,
                "Missing parameters",
                f"Please provide values for: {', '.join(missing)}",
            )
            return
        try:
            rendered = template.format(**params)
        except Exception as exc:
            QMessageBox.critical(self, "Command format error", str(exc))
            return
        self.command_requested.emit(rendered)

    def _update_param_summary(self, label: str) -> None:
        summary = self._param_summaries.get(label)
        inputs = self._param_inputs.get(label)
        if not summary or not inputs:
            return
        parts: list[str] = []
        for name, entry in inputs.items():
            value = entry.text().strip()
            if value:
                parts.append(f"{name}={value}")
        summary.setText(f"({', '.join(parts)})" if parts else "")
