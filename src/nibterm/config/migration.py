"""QSettings migration: convert old-format variable definitions to new unified format.

This module is called once at startup to migrate:
 - ``plot/column_names`` (serial CSV variables) -> ``variables/*`` with source=serial
 - ``mqtt/plot_var_*`` (MQTT plot variables)     -> ``variables/*`` with source=mqtt
 - ``plot/transform``  (transform expressions)   -> ``variables/*`` with source=transform
 - ``plot/delimiter``                             -> ``serial_parser/csv_delimiter``
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QSettings

from . import settings_keys as SK
from .variable import SerialParserConfig, VariableDefinition, load_variables, save_variables

logger = logging.getLogger(__name__)

_MIGRATION_KEY = "migration/unified_variables_done"


def migrate_settings(settings: QSettings) -> None:
    """Run all pending migrations. Safe to call on every startup."""
    if settings.value(_MIGRATION_KEY, False, bool):
        return
    _migrate_to_unified_variables(settings)
    settings.setValue(_MIGRATION_KEY, True)


def _migrate_to_unified_variables(settings: QSettings) -> None:
    """Convert old plot/column_names + mqtt/plot_var_* + plot/transform into variables/*."""
    existing = load_variables(settings)
    if existing:
        # Already have new-format variables, skip migration
        return

    variables: list[VariableDefinition] = []
    used_names: set[str] = set()

    # 1. Migrate serial CSV column names
    old_delimiter = settings.value(SK.PLOT_DELIMITER, ",", str)
    old_names_str = settings.value(SK.PLOT_COLUMN_NAMES, "", str)
    old_mqtt_indices_str = settings.value(SK.PLOT_MQTT_COLUMN_INDICES, "", str)

    # Parse old mqtt indices
    mqtt_indices: set[int] = set()
    if old_mqtt_indices_str:
        for part in old_mqtt_indices_str.split(";"):
            part = part.strip()
            if part:
                try:
                    mqtt_indices.add(int(part))
                except ValueError:
                    pass

    # Parse old column names
    if old_names_str:
        for entry in old_names_str.split(";"):
            entry = entry.strip()
            if not entry or "=" not in entry:
                continue
            idx_text, name = entry.split("=", 1)
            try:
                idx = int(idx_text.strip())
            except ValueError:
                continue
            name = name.strip()
            if not name:
                continue
            # Skip MQTT columns -- they'll be migrated from mqtt/plot_var_*
            if idx in mqtt_indices:
                continue
            if name in used_names:
                # Avoid duplicate names
                n = 2
                while f"{name}_{n}" in used_names:
                    n += 1
                name = f"{name}_{n}"
            variables.append(
                VariableDefinition(
                    name=name,
                    source="serial",
                    csv_column=idx,
                )
            )
            used_names.add(name)

    # 2. Migrate MQTT plot variables
    mqtt_count = settings.value(SK.MQTT_PLOT_VAR_COUNT, 0, int)
    for i in range(mqtt_count):
        topic = settings.value(SK.MQTT_PLOT_VAR_TOPIC.format(i), "", str)
        path = settings.value(SK.MQTT_PLOT_VAR_PATH.format(i), "", str)
        name = settings.value(SK.MQTT_PLOT_VAR_NAME.format(i), "", str)
        if not name:
            name = f"mqtt_{i}"
        if name in used_names:
            n = 2
            while f"{name}_{n}" in used_names:
                n += 1
            name = f"{name}_{n}"
        if topic or path or name:
            variables.append(
                VariableDefinition(
                    name=name,
                    source="mqtt",
                    mqtt_topic=topic,
                    json_path=path,
                )
            )
            used_names.add(name)

    # 3. Migrate transform expressions
    old_transforms_str = settings.value(SK.PLOT_TRANSFORM, "", str)
    if old_transforms_str:
        for chunk in old_transforms_str.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "=" in chunk:
                name, expr = chunk.split("=", 1)
                name = name.strip()
                expr = expr.strip()
            else:
                name = chunk
                expr = chunk
            if not expr:
                continue
            if name in used_names:
                n = 2
                while f"{name}_{n}" in used_names:
                    n += 1
                name = f"{name}_{n}"
            variables.append(
                VariableDefinition(
                    name=name or expr,
                    source="transform",
                    expression=expr,
                )
            )
            used_names.add(name)

    # 4. Save migrated variables
    if variables:
        save_variables(variables, settings)
        logger.info("Migrated %d variables from old settings format.", len(variables))

    # 5. Save serial parser config from old delimiter
    if old_delimiter and old_delimiter != ",":
        serial_config = SerialParserConfig(mode="csv", csv_delimiter=old_delimiter)
        serial_config.to_qsettings(settings)
