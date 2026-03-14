"""Dialog for configuring a per-variable regex pattern with live extraction preview."""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)


class RegexEditDialog(QDialog):
    """Configure a regex pattern and capture group for a single variable.

    Shows the test line (last received data) and a live preview of what
    value would be extracted.
    """

    def __init__(
        self,
        test_line: str = "",
        pattern: str = "",
        group: int = 1,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configure regex extraction")
        self.setMinimumWidth(500)

        # Test line display (editable so the user can type a custom test string)
        self._test_display = QPlainTextEdit()
        self._test_display.setPlainText(test_line or "")
        self._test_display.setPlaceholderText("Paste or type a test line here…")
        self._test_display.setMaximumHeight(80)
        self._test_display.textChanged.connect(self._on_test_line_changed)

        # Pattern input
        self._pattern_edit = QLineEdit(pattern)
        self._pattern_edit.setPlaceholderText(r"e.g. temp:([\d.]+)")
        self._pattern_edit.textChanged.connect(self._update_preview)

        # Group spinbox
        self._group_spin = QSpinBox()
        self._group_spin.setMinimum(0)
        self._group_spin.setMaximum(20)
        self._group_spin.setValue(group)
        self._group_spin.setToolTip("0 = entire match, 1+ = capture group number")
        self._group_spin.valueChanged.connect(self._update_preview)

        # Preview label
        self._preview_label = QLabel()
        self._preview_label.setTextFormat(Qt.TextFormat.RichText)

        # Buttons
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Test line:", self._test_display)
        form.addRow("Pattern:", self._pattern_edit)
        form.addRow("Capture group:", self._group_spin)
        form.addRow("Extracted value:", self._preview_label)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._buttons)

        self._update_preview()

    def _on_test_line_changed(self) -> None:
        self._update_preview()

    def _update_preview(self) -> None:
        pat = self._pattern_edit.text()
        grp = self._group_spin.value()
        ok_btn = self._buttons.button(QDialogButtonBox.StandardButton.Ok)

        if not pat:
            self._preview_label.setText("<i style='color:gray'>Enter a pattern above</i>")
            if ok_btn:
                ok_btn.setEnabled(False)
            return

        try:
            rx = re.compile(pat)
        except re.error as exc:
            self._preview_label.setText(
                f"<span style='color:red'>Invalid regex: {exc}</span>"
            )
            if ok_btn:
                ok_btn.setEnabled(False)
            return

        if ok_btn:
            ok_btn.setEnabled(True)

        test_line = self._test_display.toPlainText()
        if not test_line:
            self._preview_label.setText("<i style='color:gray'>No test line available</i>")
            return

        m = rx.search(test_line)
        if m is None:
            self._preview_label.setText("<span style='color:red'>no match</span>")
            return

        try:
            raw = m.group(grp)
        except IndexError:
            self._preview_label.setText(
                f"<span style='color:orange'>group {grp} does not exist in match</span>"
            )
            return

        try:
            value = float(raw)
            self._preview_label.setText(
                f"<span style='color:green'><b>{value}</b></span>"
                f"&nbsp;&nbsp;<span style='color:gray'>(raw: \"{raw}\")</span>"
            )
        except (TypeError, ValueError):
            self._preview_label.setText(
                f"<span style='color:orange'>match found but not numeric: \"{raw}\"</span>"
            )

    def pattern(self) -> str:
        return self._pattern_edit.text()

    def group(self) -> int:
        return self._group_spin.value()
