"""Dialog for configuring how serial lines are parsed (CSV or JSON)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from ..config.variable import SerialParserConfig


class SerialParserDialog(QDialog):
    """Configure serial parser: mode (CSV / JSON), delimiter, and optional JSON prefix."""

    def __init__(
        self,
        config: SerialParserConfig,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Serial parser")

        form = QFormLayout()
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("CSV", "csv")
        self._mode_combo.addItem("JSON", "json")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self._delimiter_label = QLabel("CSV delimiter")
        self._delimiter_edit = QLineEdit(config.csv_delimiter or ",")
        self._delimiter_edit.setMaxLength(4)

        self._json_prefix_label = QLabel("JSON prefix (optional)")
        self._json_prefix_edit = QLineEdit(config.json_prefix or "")
        self._json_prefix_edit.setPlaceholderText('e.g. Payload: ')
        self._json_prefix_edit.setMaxLength(200)

        form.addRow("Mode", self._mode_combo)
        form.addRow(self._delimiter_label, self._delimiter_edit)
        form.addRow(self._json_prefix_label, self._json_prefix_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        idx = self._mode_combo.findData(config.mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        self._delimiter_edit.setText(config.csv_delimiter or ",")
        self._json_prefix_edit.setText(config.json_prefix or "")
        self._on_mode_changed()

    def _on_mode_changed(self) -> None:
        is_csv = self._mode_combo.currentData() == "csv"
        is_json = self._mode_combo.currentData() == "json"
        self._delimiter_edit.setVisible(is_csv)
        self._delimiter_label.setVisible(is_csv)
        self._json_prefix_edit.setVisible(is_json)
        self._json_prefix_label.setVisible(is_json)

    def config(self) -> SerialParserConfig:
        return SerialParserConfig(
            mode=self._mode_combo.currentData(),
            csv_delimiter=self._delimiter_edit.text().strip() or ",",
            json_prefix=self._json_prefix_edit.text().strip(),
        )
