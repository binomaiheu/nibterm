from __future__ import annotations

import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class VersionBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict) -> None:
        repo_root = Path(self.root)
        target = repo_root / "src" / "nibterm" / "version.py"
        git_version = _describe_git(repo_root)
        target.write_text(f'__version__ = "{git_version}"\n', encoding="utf-8")


def _describe_git(repo_root: Path) -> str:
    try:
        output = subprocess.check_output(
            ["git", "describe", "--tags", "--dirty", "--always"],
            cwd=repo_root,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except Exception:
        return "unknown"
    return output.strip() or "unknown"


def get_build_hook():
    return VersionBuildHook
