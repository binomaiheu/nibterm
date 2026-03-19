from __future__ import annotations

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from ..config import defaults


class ConsoleWidget(QPlainTextEdit):
    line_count_changed = Signal(int, int)
    scroll_lock_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self._max_block_count = defaults.DEFAULT_CONSOLE_MAX_BLOCK_COUNT
        self._timestamp_color = defaults.DEFAULT_CONSOLE_TIMESTAMP_COLOR
        self.document().setMaximumBlockCount(self._max_block_count)
        self._line_buffer = ""
        self._display_at_line_start = True  # for timestamp at start of each line
        self._default_text_color = QColor("black")
        self._scroll_locked = False
        self._programmatic_scroll = False
        self.verticalScrollBar().valueChanged.connect(self._on_scrollbar_moved)

    def set_max_block_count(self, count: int) -> None:
        """Set the maximum number of lines kept in the console buffer."""
        self._max_block_count = count
        self.document().setMaximumBlockCount(count)
        self._emit_line_count()

    def set_timestamp_color(self, color: str) -> None:
        """Set the color used for timestamp prefixes."""
        self._timestamp_color = color

    def clear(self) -> None:
        super().clear()
        self._line_buffer = ""
        self._display_at_line_start = True
        self._emit_line_count()

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

        # Save scroll position before modifying content when locked.
        saved_scroll = self.verticalScrollBar().value() if self._scroll_locked else None

        # Display incoming text immediately (no buffering) so characters show up
        # as they arrive; only completed lines are returned for logging/plotting.
        # Normalize \r\n and \r to \n so one newline from device doesn't become two.
        display_text = text.replace("\r\n", "\n").replace("\r", "\n")
        segments = display_text.split("\n")
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for i, segment in enumerate(segments):
            # Only add timestamp when we have content to show (avoids duplicate timestamps
            # when data arrives in chunks like "\n" then "line\n", and avoids timestamp on bare \r).
            if prefix_timestamp and self._display_at_line_start and segment != "":
                ts = QDateTime.currentDateTime().toString(Qt.ISODateWithMs)
                self._insert_timestamp(cursor, ts)
                self._display_at_line_start = False
            if segment:
                cursor.insertText(segment)
            if i < len(segments) - 1:
                cursor.insertBlock()
                self._display_at_line_start = True
            elif segment == "":
                self._display_at_line_start = True

        # Restore scroll position when locked to prevent Qt's auto-scroll
        # that happens when setTextCursor moves the viewport to the cursor.
        if saved_scroll is not None:
            self._programmatic_scroll = True
            self.setTextCursor(cursor)
            self.verticalScrollBar().setValue(saved_scroll)
            self._programmatic_scroll = False
        else:
            self.setTextCursor(cursor)

        for line in lines:
            completed_lines.append(line.rstrip("\r\n"))

        if text or completed_lines:
            self._scroll_to_bottom()
            self._emit_line_count()
        return completed_lines

    def append_text(self, text: str) -> None:
        self.append_text_colored(text, None)

    def append_text_colored(self, text: str, color: str | None) -> None:
        if not text:
            return
        saved_scroll = self.verticalScrollBar().value() if self._scroll_locked else None
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if color is not None:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
        cursor.insertText(text)
        cursor.insertBlock()
        if color is not None:
            cursor.setCharFormat(QTextCharFormat())
        if saved_scroll is not None:
            self._programmatic_scroll = True
            self.setTextCursor(cursor)
            self.verticalScrollBar().setValue(saved_scroll)
            self._programmatic_scroll = False
        else:
            self.setTextCursor(cursor)
        self._scroll_to_bottom()
        self._emit_line_count()

    def append_status_message(
        self,
        message: str,
        prefix_timestamp: bool,
        color: str,
    ) -> None:
        if not message:
            return
        saved_scroll = self.verticalScrollBar().value() if self._scroll_locked else None
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if prefix_timestamp:
            ts = QDateTime.currentDateTime().toString(Qt.ISODateWithMs)
            self._insert_timestamp(cursor, ts)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(message)
        cursor.insertBlock()
        cursor.setCharFormat(QTextCharFormat())
        if saved_scroll is not None:
            self._programmatic_scroll = True
            self.setTextCursor(cursor)
            self.verticalScrollBar().setValue(saved_scroll)
            self._programmatic_scroll = False
        else:
            self.setTextCursor(cursor)
        self._scroll_to_bottom()
        self._emit_line_count()

    def _insert_timestamp(self, cursor: QTextCursor, ts: str) -> None:
        ts_format = QTextCharFormat()
        ts_format.setForeground(QColor(self._timestamp_color))
        cursor.setCharFormat(ts_format)
        cursor.insertText(f"[{ts}] ")
        cursor.setCharFormat(QTextCharFormat())

    def _scroll_to_bottom(self) -> None:
        if self._scroll_locked:
            return
        self._programmatic_scroll = True
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self._programmatic_scroll = False

    def _scroll_to_bottom_force(self) -> None:
        """Scroll to bottom regardless of lock state."""
        self._programmatic_scroll = True
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self._programmatic_scroll = False

    def _on_scrollbar_moved(self, value: int) -> None:
        if self._programmatic_scroll:
            return
        sb = self.verticalScrollBar()
        at_bottom = value >= sb.maximum() - 5
        was_locked = self._scroll_locked
        self._scroll_locked = not at_bottom
        if was_locked != self._scroll_locked:
            self.scroll_lock_changed.emit(self._scroll_locked)

    def set_scroll_locked(self, locked: bool) -> None:
        was_locked = self._scroll_locked
        self._scroll_locked = locked
        if was_locked != self._scroll_locked:
            self.scroll_lock_changed.emit(self._scroll_locked)
        if not locked:
            self._scroll_to_bottom_force()

    @property
    def is_scroll_locked(self) -> bool:
        return self._scroll_locked

    def _emit_line_count(self) -> None:
        self.line_count_changed.emit(
            self.document().blockCount(), self._max_block_count
        )
