"""Unified variable definitions and serial/topic parser configuration.

Every plottable value -- whether it comes from a serial CSV column,
a serial JSON field, a regex match, an MQTT JSON path, or a computed
transform expression -- is represented as a single ``VariableDefinition``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from PySide6.QtCore import QSettings

from . import settings_keys as SK


@dataclass
class TopicParserConfig:
    """Per-topic parser config for MQTT (same shape as SerialParserConfig)."""

    mode: str = "json"  # "csv", "json", "regex"
    csv_delimiter: str = ","


@dataclass
class SerialParserConfig:
    """Global configuration for how serial data is parsed."""

    mode: str = "csv"  # "csv", "json"
    csv_delimiter: str = ","
    json_prefix: str = ""  # optional prefix to strip before parsing JSON (e.g. "Payload: ")

    def to_qsettings(self, settings: QSettings) -> None:
        settings.setValue(SK.SERIAL_PARSER_MODE, self.mode)
        settings.setValue(SK.SERIAL_PARSER_CSV_DELIMITER, self.csv_delimiter)
        settings.setValue(SK.SERIAL_PARSER_JSON_PREFIX, self.json_prefix)

    @staticmethod
    def from_qsettings(settings: QSettings) -> "SerialParserConfig":
        return SerialParserConfig(
            mode=settings.value(SK.SERIAL_PARSER_MODE, "csv", str),
            csv_delimiter=settings.value(SK.SERIAL_PARSER_CSV_DELIMITER, ",", str),
            json_prefix=settings.value(SK.SERIAL_PARSER_JSON_PREFIX, "", str),
        )


@dataclass
class VariableDefinition:
    """A single plottable variable, regardless of source."""

    name: str = ""
    source: str = "serial"  # "serial", "mqtt", "transform"
    unit: str = ""  # optional, used in plot axis/legend labels

    # Serial fields (interpretation depends on SerialParserConfig.mode)
    csv_column: int = 0
    json_path: str = ""  # also used for MQTT
    regex_pattern: str = ""
    regex_group: int = 1

    # MQTT-specific
    mqtt_topic: str = ""

    # Transform-specific
    expression: str = ""

    def extraction_key(self) -> tuple:
        """Immutable key that identifies the same extraction (ignores name/unit)."""
        return (
            self.source,
            self.csv_column,
            self.json_path,
            self.regex_pattern,
            self.regex_group,
            self.mqtt_topic,
            self.expression,
        )

    def details_summary(self, serial_mode: str = "csv") -> str:
        """Human-readable summary of the extraction config."""
        if self.source == "serial":
            if serial_mode == "csv":
                return f"CSV column {self.csv_column}"
            if serial_mode == "json":
                return self.json_path or "(no path)"
            if serial_mode == "regex":
                pat = self.regex_pattern or "(no pattern)"
                return f"{pat} group {self.regex_group}"
            return "?"
        if self.source == "mqtt":
            topic = self.mqtt_topic or "*"
            path = self.json_path or "$"
            return f"{topic} → {path}"
        if self.source == "transform":
            return self.expression or "(no expression)"
        return ""


def save_variables(variables: list[VariableDefinition], settings: QSettings) -> None:
    """Persist the variable list to QSettings."""
    settings.setValue(SK.VAR_COUNT, len(variables))
    for i, v in enumerate(variables):
        prefix = SK.VAR_PREFIX.format(i)
        settings.setValue(f"{prefix}/name", v.name)
        settings.setValue(f"{prefix}/source", v.source)
        settings.setValue(f"{prefix}/csv_column", v.csv_column)
        settings.setValue(f"{prefix}/json_path", v.json_path)
        settings.setValue(f"{prefix}/regex_pattern", v.regex_pattern)
        settings.setValue(f"{prefix}/regex_group", v.regex_group)
        settings.setValue(f"{prefix}/mqtt_topic", v.mqtt_topic)
        settings.setValue(f"{prefix}/expression", v.expression)
        settings.setValue(f"{prefix}/unit", v.unit)


def load_variables(settings: QSettings) -> list[VariableDefinition]:
    """Restore the variable list from QSettings."""
    count = settings.value(SK.VAR_COUNT, 0, int)
    variables: list[VariableDefinition] = []
    for i in range(count):
        prefix = SK.VAR_PREFIX.format(i)
        name = settings.value(f"{prefix}/name", "", str)
        if not name:
            continue
        variables.append(
            VariableDefinition(
                name=name,
                source=settings.value(f"{prefix}/source", "serial", str),
                unit=settings.value(f"{prefix}/unit", "", str),
                csv_column=settings.value(f"{prefix}/csv_column", 0, int),
                json_path=settings.value(f"{prefix}/json_path", "", str),
                regex_pattern=settings.value(f"{prefix}/regex_pattern", "", str),
                regex_group=settings.value(f"{prefix}/regex_group", 1, int),
                mqtt_topic=settings.value(f"{prefix}/mqtt_topic", "", str),
                expression=settings.value(f"{prefix}/expression", "", str),
            )
        )
    return variables


def load_topic_parser_configs(settings: QSettings) -> dict[str, "TopicParserConfig"]:
    """Load per-topic parser configs from QSettings (JSON blob)."""
    raw = settings.value(SK.MQTT_TOPIC_PARSERS, "", str)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    result: dict[str, TopicParserConfig] = {}
    for topic, cfg in data.items():
        if isinstance(cfg, dict):
            result[str(topic)] = TopicParserConfig(
                mode=cfg.get("mode", "json"),
                csv_delimiter=cfg.get("csv_delimiter", ","),
            )
    return result


def save_topic_parser_configs(
    configs: dict[str, TopicParserConfig], settings: QSettings
) -> None:
    """Persist per-topic parser configs to QSettings (JSON blob)."""
    data = {
        topic: {"mode": c.mode, "csv_delimiter": c.csv_delimiter}
        for topic, c in configs.items()
    }
    settings.setValue(SK.MQTT_TOPIC_PARSERS, json.dumps(data))
