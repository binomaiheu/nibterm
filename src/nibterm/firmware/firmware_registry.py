from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FirmwareFile:
    path: Path
    filename: str
    version: str


def _version_sort_key(version: str) -> tuple[int, ...]:
    """Convert a version string like '1.2.3' into a tuple for sorting."""
    parts: list[int] = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


class FirmwareRegistry:
    def __init__(self, folder: str | Path) -> None:
        self._folder = Path(folder)

    @property
    def folder(self) -> Path:
        return self._folder

    def scan(self, file_glob: str, version_pattern: str) -> list[FirmwareFile]:
        """Scan the firmware folder and return matching files sorted by version descending."""
        if not self._folder.is_dir():
            return []

        results: list[FirmwareFile] = []
        for path in self._folder.glob(file_glob):
            if not path.is_file():
                continue
            # Match version pattern against the relative path so patterns
            # that include parent directory names (e.g. version-tagged folders)
            # can be used.
            rel_path = path.relative_to(self._folder).as_posix()
            match = re.search(version_pattern, rel_path)
            version = match.group(1) if match else "unknown"
            results.append(FirmwareFile(path=path, filename=path.name, version=version))

        results.sort(key=lambda f: _version_sort_key(f.version), reverse=True)
        return results
