from __future__ import annotations

from pathlib import Path


class FileLogger:
    def __init__(self) -> None:
        self._file = None
        self._path: Path | None = None

    def start(self, path: str | Path) -> None:
        self.stop()
        self._path = Path(path)
        self._file = self._path.open("a", encoding="utf-8")

    def stop(self) -> None:
        if self._file:
            self._file.close()
        self._file = None

    def is_active(self) -> bool:
        return self._file is not None

    def log_line(self, line: str) -> None:
        if not self._file:
            return
        self._file.write(f"{line}\n")
        self._file.flush()
