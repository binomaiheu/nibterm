from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo

# Tried in order when the requested family is missing or not fixed-pitch.
_PREFERRED_MONOSPACE = ("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono")


def _is_usable(font: QFont, family: str) -> bool:
    # A differing family means Qt substituted it (e.g. "Monospace" on Windows).
    info = QFontInfo(font)
    return info.fixedPitch() and info.family().lower() == family.lower()


def monospace_font(family: str | None = None, size: int = 10) -> QFont:
    """Return a fixed-pitch font, falling back to a known monospace font.

    Generic names like "Monospace" only exist on Linux (fontconfig); on
    Windows/macOS Qt would otherwise substitute a proportional font.
    """
    font = QFont(family) if family else QFont()
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    if not family or not _is_usable(font, family):
        families = set(QFontDatabase.families())
        for candidate in _PREFERRED_MONOSPACE:
            if candidate in families:
                font = QFont(candidate)
                break
        else:
            font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(size)
    return font
