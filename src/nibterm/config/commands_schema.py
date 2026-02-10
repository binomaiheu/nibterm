from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class CommandParam:
    name: str
    label: str | None = None
    default: str | None = None
    description: str | None = None


@dataclass
class Command:
    label: str
    command: str
    color: str | None = None
    params: list[CommandParam] | None = None
    description: str | None = None


@dataclass
class CommandPreset:
    name: str
    commands: list[Command]


def load_preset(path: str | Path) -> CommandPreset:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Preset file must be a YAML mapping.")

    preset_name = raw.get("name")
    commands = raw.get("commands")
    if not isinstance(preset_name, str) or not preset_name:
        raise ValueError("Preset must include a non-empty 'name'.")
    if not isinstance(commands, list):
        raise ValueError("Preset must include a 'commands' list.")

    parsed: list[Command] = []
    for entry in commands:
        if not isinstance(entry, dict):
            raise ValueError("Each command must be a mapping with label and command.")
        label = entry.get("label")
        command = entry.get("command")
        color = entry.get("color")
        params_raw = entry.get("params", [])
        description = entry.get("description")
        if not isinstance(label, str) or not isinstance(command, str):
            raise ValueError("Command entries must include 'label' and 'command' strings.")
        if color is not None and not isinstance(color, str):
            raise ValueError("'color' must be a string if provided.")
        if description is not None and not isinstance(description, str):
            raise ValueError("'description' must be a string if provided.")
        params: list[CommandParam] = []
        if params_raw:
            if not isinstance(params_raw, list):
                raise ValueError("'params' must be a list.")
            for param in params_raw:
                if not isinstance(param, dict):
                    raise ValueError("Each param must be a mapping.")
                param_name = param.get("name")
                if not isinstance(param_name, str) or not param_name:
                    raise ValueError("Param must include a non-empty 'name'.")
                label_text = param.get("label")
                if label_text is not None and not isinstance(label_text, str):
                    raise ValueError("'label' must be a string if provided.")
                default = param.get("default")
                if default is not None and not isinstance(default, str):
                    default = str(default)
                param_description = param.get("description")
                if param_description is not None and not isinstance(param_description, str):
                    raise ValueError("'description' must be a string if provided.")
                params.append(
                    CommandParam(
                        name=param_name,
                        label=label_text,
                        default=default,
                        description=param_description,
                    )
                )
        parsed.append(
            Command(
                label=label,
                command=command,
                color=color,
                params=params,
                description=description,
            )
        )

    return CommandPreset(name=preset_name, commands=parsed)
