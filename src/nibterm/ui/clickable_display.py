"""Shared clickable text display for CSV columns and JSON paths (MQTT and Serial plot panels)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QMouseEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit


def build_csv_column_ranges(
    line: str, delimiter: str
) -> list[tuple[int, int, str, str]]:
    """Return (start, end, path, key_name) for each CSV column for click-to-add.

    path is \"__column_0\", \"__column_1\", ... so the callback can add by column index.
    """
    if not delimiter:
        delimiter = ","
    ranges: list[tuple[int, int, str, str]] = []
    pos = 0
    col = 0
    while True:
        next_delim = line.find(delimiter, pos)
        if next_delim == -1:
            key = line[pos:].strip() or f"col{col}"
            ranges.append((pos, len(line), f"__column_{col}", key))
            break
        key = line[pos:next_delim].strip() or f"col{col}"
        ranges.append((pos, next_delim, f"__column_{col}", key))
        col += 1
        pos = next_delim + len(delimiter)
    return ranges


class PathClickableEdit(QPlainTextEdit):
    """Read-only plain text edit that notifies on click when a path/column is hit.

    Used for JSON paths (MQTT) and CSV columns (Serial/MQTT). path_ranges are
    (start, end, path, key_name). Highlights plot-variable paths and hover range.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._path_ranges: list[tuple[int, int, str, str]] = []
        self._on_path_clicked: Callable[[str, str], None] | None = None
        self._plot_variable_paths: set[str] = set()
        self._hover_range: tuple[int, int] | None = None
        self.setMouseTracking(True)

    def set_path_ranges(self, ranges: list[tuple[int, int, str, str]]) -> None:
        self._path_ranges = ranges
        self._hover_range = None
        self._update_highlights()

    def set_plot_variable_paths(self, paths: set[str]) -> None:
        """Set paths that are already in the plot table (for highlight)."""
        self._plot_variable_paths = paths
        self._update_highlights()

    def set_on_path_clicked(self, callback: Callable[[str, str], None] | None) -> None:
        self._on_path_clicked = callback

    def _offset_at(self, pos: QPoint) -> int:
        cursor = self.cursorForPosition(pos)
        block = cursor.block()
        return block.position() + cursor.positionInBlock()

    def _range_at_offset(self, offset: int) -> tuple[int, int] | None:
        for start, end, _path, _key in self._path_ranges:
            if start <= offset < end:
                return (start, end)
        return None

    def _update_highlights(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        doc = self.document()
        for start, end, path, _key in self._path_ranges:
            in_table = path in self._plot_variable_paths
            is_hover = (start, end) == self._hover_range
            if is_hover:
                fmt = QTextCharFormat()
                fmt.setBackground(QColor("#b3d9ff"))  # light blue on hover
            elif in_table:
                fmt = QTextCharFormat()
                fmt.setBackground(QColor("#e6f3ff"))  # very light blue for "in table"
            else:
                continue
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = QTextCursor(doc)
            sel.cursor.setPosition(start)
            sel.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            selections.append(sel)
        self.setExtraSelections(selections)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if not self._path_ranges:
            return
        offset = self._offset_at(event.pos())
        new_range = self._range_at_offset(offset)
        if new_range != self._hover_range:
            self._hover_range = new_range
            self._update_highlights()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        if self._hover_range is not None:
            self._hover_range = None
            self._update_highlights()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() != Qt.MouseButton.LeftButton or not self._path_ranges:
            return
        offset = self._offset_at(event.pos())
        for start, end, path, key_name in self._path_ranges:
            if start <= offset < end and self._on_path_clicked:
                self._on_path_clicked(path, key_name)
                break
