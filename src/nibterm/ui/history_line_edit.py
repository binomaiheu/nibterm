from __future__ import annotations

from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QLineEdit

from ..config import defaults
from ..config import settings_keys as SK


class CommandHistoryLineEdit(QLineEdit):
    """QLineEdit with command history (Up/Down) and reverse search (Ctrl+R)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._history: list[str] = []
        self._history_index: int = -1
        self._saved_input: str = ""
        self._max_length: int = defaults.DEFAULT_HISTORY_MAX_LENGTH

        self._search_active: bool = False
        self._search_query: str = ""
        self._search_match_index: int = -1
        self._saved_placeholder: str = ""
        self._saved_stylesheet: str = ""

    # -- public API ----------------------------------------------------------

    def set_max_length(self, n: int) -> None:
        self._max_length = max(1, n)
        if len(self._history) > self._max_length:
            self._history = self._history[-self._max_length :]

    def add_entry(self, text: str) -> None:
        if not text:
            return
        # Skip consecutive duplicates
        if self._history and self._history[-1] == text:
            self._history_index = -1
            return
        self._history.append(text)
        if len(self._history) > self._max_length:
            self._history = self._history[-self._max_length :]
        self._history_index = -1

    def load_from_settings(self, settings: QSettings) -> None:
        entries = settings.value(SK.HISTORY_ENTRIES, [], list)
        if isinstance(entries, list):
            self._history = [str(e) for e in entries]
        self._max_length = settings.value(
            SK.HISTORY_MAX_LENGTH, defaults.DEFAULT_HISTORY_MAX_LENGTH, int
        )
        if len(self._history) > self._max_length:
            self._history = self._history[-self._max_length :]

    def save_to_settings(self, settings: QSettings) -> None:
        settings.setValue(SK.HISTORY_ENTRIES, self._history)
        settings.setValue(SK.HISTORY_MAX_LENGTH, self._max_length)

    @property
    def history(self) -> list[str]:
        return self._history

    # -- key handling --------------------------------------------------------

    def event(self, event: QEvent) -> bool:
        # Intercept Tab before Qt's focus-navigation handles it.
        if (
            self._search_active
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Tab
        ):
            self._exit_search()
            return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._search_active:
            self._handle_search_key(event)
            return

        if event.key() == Qt.Key.Key_Up:
            self._navigate_up()
            return
        if event.key() == Qt.Key.Key_Down:
            self._navigate_down()
            return
        if (
            event.key() == Qt.Key.Key_R
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self._start_search()
            return

        # Any other key resets history browsing
        self._history_index = -1
        super().keyPressEvent(event)

    # -- history navigation --------------------------------------------------

    def _navigate_up(self) -> None:
        if not self._history:
            return
        if self._history_index == -1:
            self._saved_input = self.text()
            self._history_index = len(self._history) - 1
        elif self._history_index > 0:
            self._history_index -= 1
        self.setText(self._history[self._history_index])

    def _navigate_down(self) -> None:
        if self._history_index == -1:
            return
        self._history_index += 1
        if self._history_index >= len(self._history):
            self._history_index = -1
            self.setText(self._saved_input)
        else:
            self.setText(self._history[self._history_index])

    # -- reverse search (Ctrl+R) --------------------------------------------

    def _start_search(self) -> None:
        self._saved_input = self.text()
        self._search_active = True
        self._search_query = ""
        self._search_match_index = len(self._history) - 1
        self._saved_placeholder = self.placeholderText()
        self._saved_stylesheet = self.styleSheet()
        self.setStyleSheet("background-color: #fff9c4;")
        self._update_search_display()

    def _exit_search(self, restore: bool = False) -> None:
        self._search_active = False
        self._history_index = -1
        self.setPlaceholderText(self._saved_placeholder)
        self.setStyleSheet(self._saved_stylesheet)
        if restore:
            self.setText(self._saved_input)

    def _handle_search_key(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._exit_search(restore=True)
            return

        if event.key() == Qt.Key.Key_Tab:
            # Accept current match
            self._exit_search()
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Accept match and send
            self._exit_search()
            self.returnPressed.emit()
            return

        if (
            event.key() == Qt.Key.Key_R
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            # Search for next match backwards
            if self._search_match_index > 0:
                self._search_match_index -= 1
                self._perform_search()
            return

        if event.key() == Qt.Key.Key_Backspace:
            if self._search_query:
                self._search_query = self._search_query[:-1]
                self._search_match_index = len(self._history) - 1
                self._perform_search()
            return

        # Printable character — append to search query
        text = event.text()
        if text and text.isprintable():
            self._search_query += text
            self._perform_search()
            return

        # Any other key (arrows, Home, End, etc.) exits search and passes through
        self._exit_search()
        super().keyPressEvent(event)

    def _perform_search(self) -> None:
        if not self._search_query:
            self._update_search_display()
            return

        query_lower = self._search_query.lower()
        for i in range(self._search_match_index, -1, -1):
            if query_lower in self._history[i].lower():
                self._search_match_index = i
                self.setText(self._history[i])
                self._update_search_display()
                return

        # No match found
        self._update_search_display(failing=True)

    def _update_search_display(self, failing: bool = False) -> None:
        prefix = "failing " if failing else ""
        self.setPlaceholderText(f"({prefix}reverse-i-search): {self._search_query}")
