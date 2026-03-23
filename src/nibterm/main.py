import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow

# Resolve static dir: repo root when running from source, or bundled
_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
if not _STATIC_DIR.exists():
    _STATIC_DIR = Path(__file__).resolve().parent / "static"


def main() -> None:
    parser = argparse.ArgumentParser(description="nibterm serial terminal")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="enable debug logging"
    )
    args, remaining = parser.parse_known_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")

    app = QApplication(remaining)
    icon_path = _STATIC_DIR / "nibterm-icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
