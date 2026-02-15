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
class CommandOption:
    flag: str
    label: str | None = None
    type: str = "bool"  # "bool" | "value"
    default: bool | str | None = None
    description: str | None = None


@dataclass
class Command:
    label: str
    command: str
    color: str | None = None
    params: list[CommandParam] | None = None
    options: list[CommandOption] | None = None
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
        options_raw = entry.get("options", [])
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
        options: list[CommandOption] = []
        if options_raw:
            if not isinstance(options_raw, list):
                raise ValueError("'options' must be a list.")
            for opt in options_raw:
                if not isinstance(opt, dict):
                    raise ValueError("Each option must be a mapping.")
                flag = opt.get("flag")
                if not isinstance(flag, str) or not flag.strip():
                    raise ValueError("Option must include a non-empty 'flag'.")
                flag = flag.strip()
                opt_label = opt.get("label")
                if opt_label is not None and not isinstance(opt_label, str):
                    raise ValueError("'label' must be a string if provided.")
                opt_type = opt.get("type", "bool")
                if opt_type not in ("bool", "value"):
                    raise ValueError("Option 'type' must be 'bool' or 'value'.")
                opt_default = opt.get("default")
                if opt_type == "bool":
                    if opt_default is not None and not isinstance(opt_default, bool):
                        raise ValueError("Boolean option 'default' must be true/false if provided.")
                else:
                    if opt_default is not None:
                        opt_default = str(opt_default)
                opt_description = opt.get("description")
                if opt_description is not None and not isinstance(opt_description, str):
                    raise ValueError("'description' must be a string if provided.")
                options.append(
                    CommandOption(
                        flag=flag,
                        label=opt_label,
                        type=opt_type,
                        default=opt_default,
                        description=opt_description,
                    )
                )
        parsed.append(
            Command(
                label=label,
                command=command,
                color=color,
                params=params,
                options=options,
                description=description,
            )
        )

    return CommandPreset(name=preset_name, commands=parsed)
