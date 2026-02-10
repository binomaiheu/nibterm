from __future__ import annotations

from __future__ import annotations

from PySide6.QtCore import QDateTime
from PySide6.QtGui import QColor, QFont, QPalette, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit


class ConsoleWidget(QPlainTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(5000)
        self._line_buffer = ""
        self._default_text_color = QColor("black")

    def set_appearance(
        self,
        font_family: str,
        font_size: int,
        background_color: str,
        text_color: str,
    ) -> None:
        font = QFont(font_family, font_size)
        self.setFont(font)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(background_color))
        self._default_text_color = QColor(text_color)
        palette.setColor(QPalette.ColorRole.Text, self._default_text_color)
        self.setPalette(palette)

    def append_data(self, text: str, prefix_timestamp: bool) -> list[str]:
        if not text:
            return []

        self._line_buffer += text
        lines = self._line_buffer.splitlines(keepends=True)

        completed_lines: list[str] = []
        if lines and not lines[-1].endswith(("\n", "\r")):
            self._line_buffer = lines.pop()
        else:
            self._line_buffer = ""

        for line in lines:
            stripped = line.rstrip("\r\n")
            completed_lines.append(stripped)
            display_line = stripped
            if prefix_timestamp:
                ts = QDateTime.currentDateTime().toString("HH:mm:ss.zzz")
                display_line = f"[{ts}] {display_line}"
            self.appendPlainText(display_line)

        if completed_lines:
            self._scroll_to_bottom()
        return completed_lines

    def append_text(self, text: str) -> None:
        self.append_text_colored(text, None)

    def append_text_colored(self, text: str, color: str | None) -> None:
        if not text:
            return
        if color is None:
            self.appendPlainText(text)
        else:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
            cursor.insertText(text)
            cursor.insertBlock()
            cursor.setCharFormat(QTextCharFormat())
            self.setTextCursor(cursor)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
