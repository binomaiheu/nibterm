from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Device:
    name: str
    label: str
    executable: str
    args: str
    version_pattern: str
    file_glob: str
    pre_upload_delay_ms: int = 0


@dataclass
class FirmwareConfig:
    firmware_folder: str
    log_folder: str | None
    devices: list[Device]


def load_firmware_config(path: str | Path) -> FirmwareConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Firmware config file must be a YAML mapping.")

    firmware_folder = raw.get("firmware_folder")
    if not isinstance(firmware_folder, str) or not firmware_folder:
        raise ValueError("Config must include a non-empty 'firmware_folder'.")

    log_folder = raw.get("log_folder")
    if log_folder is not None and not isinstance(log_folder, str):
        raise ValueError("'log_folder' must be a string if provided.")

    devices_raw = raw.get("devices")
    if not isinstance(devices_raw, list) or not devices_raw:
        raise ValueError("Config must include a non-empty 'devices' list.")

    devices: list[Device] = []
    seen_names: set[str] = set()
    for entry in devices_raw:
        if not isinstance(entry, dict):
            raise ValueError("Each device must be a mapping.")

        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("Device must include a non-empty 'name'.")
        if name in seen_names:
            raise ValueError(f"Duplicate device name: '{name}'.")
        seen_names.add(name)

        label = entry.get("label")
        if not isinstance(label, str) or not label:
            raise ValueError(f"Device '{name}' must include a non-empty 'label'.")

        executable = entry.get("executable")
        if not isinstance(executable, str) or not executable:
            raise ValueError(f"Device '{name}' must include a non-empty 'executable'.")

        args = entry.get("args")
        if not isinstance(args, str):
            raise ValueError(f"Device '{name}' must include an 'args' string.")

        version_pattern = entry.get("version_pattern")
        if not isinstance(version_pattern, str) or not version_pattern:
            raise ValueError(f"Device '{name}' must include a non-empty 'version_pattern'.")

        file_glob = entry.get("file_glob")
        if not isinstance(file_glob, str) or not file_glob:
            raise ValueError(f"Device '{name}' must include a non-empty 'file_glob'.")

        pre_upload_delay_ms = entry.get("pre_upload_delay_ms", 0)
        if not isinstance(pre_upload_delay_ms, int):
            raise ValueError(f"Device '{name}': 'pre_upload_delay_ms' must be an integer.")

        devices.append(
            Device(
                name=name,
                label=label,
                executable=executable,
                args=args,
                version_pattern=version_pattern,
                file_glob=file_glob,
                pre_upload_delay_ms=pre_upload_delay_ms,
            )
        )

    return FirmwareConfig(
        firmware_folder=firmware_folder,
        log_folder=log_folder,
        devices=devices,
    )
