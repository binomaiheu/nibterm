import argparse
import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .config.paths import static_dir
from .main_window import MainWindow


def main() -> None:
    parser = argparse.ArgumentParser(description="nibterm serial terminal")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="enable debug logging"
    )
    args, remaining = parser.parse_known_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")

    app = QApplication(remaining)
    app.setStyle("Fusion")
    icon_path = static_dir() / "nibterm-icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
