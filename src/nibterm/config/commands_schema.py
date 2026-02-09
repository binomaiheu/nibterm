from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Command:
    label: str
    command: str


@dataclass
class CommandPreset:
    name: str
    commands: list[Command]


def load_preset(path: str | Path) -> CommandPreset:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Preset file must be a YAML mapping.")

    name = raw.get("name")
    commands = raw.get("commands")
    if not isinstance(name, str) or not name:
        raise ValueError("Preset must include a non-empty 'name'.")
    if not isinstance(commands, list):
        raise ValueError("Preset must include a 'commands' list.")

    parsed: list[Command] = []
    for entry in commands:
        if not isinstance(entry, dict):
            raise ValueError("Each command must be a mapping with label and command.")
        label = entry.get("label")
        command = entry.get("command")
        if not isinstance(label, str) or not isinstance(command, str):
            raise ValueError("Command entries must include 'label' and 'command' strings.")
        parsed.append(Command(label=label, command=command))

    return CommandPreset(name=name, commands=parsed)
