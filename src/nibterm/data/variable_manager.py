"""Unified variable manager -- the single source of truth for all plottable variables.

Replaces ``PlotDataAggregator`` and the ad-hoc MQTT/serial variable merging
that previously lived in ``MainWindow`` and ``MQTTMonitorWidget``.
"""
from __future__ import annotations

import logging
from dataclasses import replace

from PySide6.QtCore import QObject, QSettings, Signal

from ..config.variable import (
    SerialParserConfig,
    TopicParserConfig,
    VariableDefinition,
    load_topic_parser_configs,
    load_variables,
    save_topic_parser_configs,
    save_variables,
)
from .json_utils import extract_json_value, unique_variable_name
from .parsers import parse_csv_line, parse_json_payload, parse_regex_value
from .transforms import (
    get_expression_variable_names,
    rewrite_expression_rename,
    safe_eval,
)

logger = logging.getLogger(__name__)


class VariableManager(QObject):
    """Central store and processor for all defined variables.

    Signals
    -------
    variables_changed
        Emitted whenever the variable list is added to, removed from,
        or edited (including reorder).
    values_updated
        Emitted whenever stored values change (e.g. after serial line or MQTT).
    """

    variables_changed = Signal()
    values_updated = Signal()

    def __init__(self, settings: QSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._variables: list[VariableDefinition] = load_variables(settings)
        self._serial_config = SerialParserConfig.from_qsettings(settings)
        self._topic_parser_configs: dict[str, TopicParserConfig] = (
            load_topic_parser_configs(settings)
        )
        self._values: dict[str, float] = {}
        self._last_serial_line: str = ""  # for Serial Plot variables panel (last line display and click-to-add CSV columns)

    # -- persistence ----------------------------------------------------------

    def save(self) -> None:
        save_variables(self._variables, self._settings)
        self._serial_config.to_qsettings(self._settings)
        save_topic_parser_configs(self._topic_parser_configs, self._settings)

    # -- accessors ------------------------------------------------------------

    @property
    def variables(self) -> list[VariableDefinition]:
        return list(self._variables)

    @property
    def serial_config(self) -> SerialParserConfig:
        return self._serial_config

    def get_values(self) -> dict[str, float]:
        """Return a snapshot of last-known values for every variable."""
        return dict(self._values)

    def get_variable_names(self) -> list[str]:
        return [v.name for v in self._variables]

    def get_variable_list(self) -> list[tuple[str, str]]:
        """Return ``(name, display_label)`` for each variable.

        When unit is set, display_label is ``name (unit)``; otherwise ``name (source)``.
        """
        result: list[tuple[str, str]] = []
        for v in self._variables:
            if v.unit:
                label = f"{v.name} ({v.unit})"
            else:
                label = f"{v.name} ({v.source})"
            result.append((v.name, label))
        return result

    def get_mqtt_variables(self) -> list[VariableDefinition]:
        """Return only the MQTT-sourced variables."""
        return [v for v in self._variables if v.source == "mqtt"]

    def get_serial_variables(self) -> list[VariableDefinition]:
        """Return only the serial-sourced variables."""
        return [v for v in self._variables if v.source == "serial"]

    # -- CRUD -----------------------------------------------------------------

    def add_variable(self, var: VariableDefinition) -> None:
        existing = {v.name for v in self._variables}
        var.name = unique_variable_name(var.name or "var", existing)
        self._variables.append(var)
        self.save()
        self.variables_changed.emit()

    def remove_variable(self, name: str) -> None:
        # Remove this variable and any transforms that depend on it (recursively)
        to_remove: set[str] = {name}
        while True:
            dependents = self._transforms_depending_on(to_remove)
            if dependents <= to_remove:
                break
            to_remove |= dependents
        for n in to_remove:
            self._values.pop(n, None)
        self._variables = [v for v in self._variables if v.name not in to_remove]
        self.save()
        self.variables_changed.emit()

    def _transforms_depending_on(self, names: set[str]) -> set[str]:
        """Return names of transform variables whose expression references any of the given names."""
        dependents: set[str] = set()
        for v in self._variables:
            if v.source == "transform" and v.expression:
                refs = get_expression_variable_names(v.expression)
                if refs & names:
                    dependents.add(v.name)
        return dependents

    def remove_all_mqtt_variables(self) -> None:
        """Remove all MQTT-sourced variables and any transforms that depend on them."""
        removed = {v.name for v in self._variables if v.source == "mqtt"}
        while True:
            dependents = self._transforms_depending_on(removed)
            if dependents <= removed:
                break
            removed |= dependents
        self._variables = [v for v in self._variables if v.name not in removed]
        for name in removed:
            self._values.pop(name, None)
        self.save()
        self.variables_changed.emit()

    def remove_all_serial_variables(self) -> None:
        """Remove all serial-sourced variables and any transforms that depend on them."""
        removed = {v.name for v in self._variables if v.source == "serial"}
        while True:
            dependents = self._transforms_depending_on(removed)
            if dependents <= removed:
                break
            removed |= dependents
        self._variables = [v for v in self._variables if v.name not in removed]
        for name in removed:
            self._values.pop(name, None)
        self.save()
        self.variables_changed.emit()

    def update_variable(self, old_name: str, new_var: VariableDefinition) -> None:
        existing = {v.name for v in self._variables if v.name != old_name}
        if new_var.name in existing:
            new_var = replace(
                new_var,
                name=unique_variable_name(new_var.name, existing),
            )
        for i, v in enumerate(self._variables):
            if v.name == old_name:
                if new_var.name != old_name:
                    val = self._values.pop(old_name, None)
                    if val is not None:
                        self._values[new_var.name] = val
                    # Update transform expressions that reference the old name
                    for idx_t, t in enumerate(self._variables):
                        if t.source == "transform" and t.expression:
                            refs = get_expression_variable_names(t.expression)
                            if old_name in refs:
                                new_expr = rewrite_expression_rename(
                                    t.expression, old_name, new_var.name
                                )
                                self._variables[idx_t] = replace(t, expression=new_expr)
                self._variables[i] = new_var
                break
        self.save()
        self.variables_changed.emit()

    def set_variables(self, variables: list[VariableDefinition]) -> None:
        """Replace the entire variable list (e.g. from the Variables dialog).
        Enforces unique names, migrates values on rename, and updates transform
        expressions when a referenced variable is renamed.
        """
        # Enforce unique names
        used: set[str] = set()
        unique_list: list[VariableDefinition] = []
        for v in variables:
            name = unique_variable_name(v.name or "var", used)
            used.add(name)
            unique_list.append(replace(v, name=name))

        old_by_key = {v.extraction_key(): v for v in self._variables}
        renames: dict[str, str] = {}
        for new_var in unique_list:
            old_var = old_by_key.get(new_var.extraction_key())
            if old_var is not None and old_var.name != new_var.name:
                renames[old_var.name] = new_var.name

        # Update transform expressions to use new names
        for i, v in enumerate(unique_list):
            if v.source == "transform" and v.expression:
                expr = v.expression
                for old_n, new_n in renames.items():
                    expr = rewrite_expression_rename(expr, old_n, new_n)
                unique_list[i] = replace(v, expression=expr)

        # Migrate values for renames
        for new_var in unique_list:
            old_var = old_by_key.get(new_var.extraction_key())
            if old_var is not None and old_var.name != new_var.name:
                val = self._values.pop(old_var.name, None)
                if val is not None:
                    self._values[new_var.name] = val

        self._variables = unique_list
        valid_names = {v.name for v in self._variables}
        self._values = {k: v for k, v in self._values.items() if k in valid_names}
        self.save()
        self.variables_changed.emit()

    def set_serial_config(self, config: SerialParserConfig) -> None:
        self._serial_config = config
        self.save()

    def get_topic_parser_config(self, topic: str) -> TopicParserConfig:
        """Return parser config for topic; default JSON if not set."""
        return self._topic_parser_configs.get(
            topic, TopicParserConfig(mode="json", csv_delimiter=",")
        )

    def set_topic_parser_config(self, topic: str, config: TopicParserConfig) -> None:
        self._topic_parser_configs[topic] = config
        self.save()

    def get_last_serial_line(self) -> str:
        """Last line received from serial (for Serial Plot variables panel)."""
        return self._last_serial_line

    def set_last_serial_line(self, line: str) -> None:
        """Set last serial line so the Serial Plot variables panel can display it."""
        self._last_serial_line = line
        self.values_updated.emit()

    # -- data processing ------------------------------------------------------

    def process_serial_line(self, line: str) -> tuple[dict[str, float], set[str]]:
        """Parse *line* according to the current serial parser mode.

        Returns ``(all_values, updated_names)`` where *updated_names*
        contains only the variable names that were freshly parsed from
        this line.
        """
        self._last_serial_line = line
        updated: set[str] = set()
        serial_vars = [v for v in self._variables if v.source == "serial"]
        if not serial_vars:
            return self.get_values(), updated

        mode = self._serial_config.mode

        if mode == "csv":
            self._parse_csv(line, serial_vars, updated)
        elif mode == "json":
            self._parse_serial_json(line, serial_vars, updated)
        elif mode == "regex":
            self._parse_serial_regex(line, serial_vars, updated)

        # Evaluate transforms
        self._evaluate_transforms(updated)
        self.values_updated.emit()
        return self.get_values(), updated

    def process_mqtt_values(self, values_by_name: dict[str, float]) -> tuple[dict[str, float], set[str]]:
        """Merge MQTT-extracted values and evaluate transforms.

        Returns ``(all_values, updated_names)``.
        """
        updated: set[str] = set()
        for name, value in values_by_name.items():
            self._values[name] = value
            updated.add(name)

        self._evaluate_transforms(updated)
        self.values_updated.emit()
        return self.get_values(), updated

    # -- internal parsers (use shared parsers module) -------------------------

    def _parse_csv(
        self,
        line: str,
        serial_vars: list[VariableDefinition],
        updated: set[str],
    ) -> None:
        delim = self._serial_config.csv_delimiter
        column_values = parse_csv_line(line, delim, column_indices=None)
        for v in serial_vars:
            if v.csv_column not in column_values:
                continue
            self._values[v.name] = column_values[v.csv_column]
            updated.add(v.name)

    def _parse_serial_json(
        self,
        line: str,
        serial_vars: list[VariableDefinition],
        updated: set[str],
    ) -> None:
        text = line.strip()
        prefix = (self._serial_config.json_prefix or "").strip()
        if prefix and text.startswith(prefix):
            text = text[len(prefix) :].strip()
        obj = parse_json_payload(text)
        if obj is None:
            return
        for v in serial_vars:
            if not v.json_path:
                continue
            val = extract_json_value(obj, v.json_path)
            if val is not None:
                self._values[v.name] = val
                updated.add(v.name)

    def _parse_serial_regex(
        self,
        line: str,
        serial_vars: list[VariableDefinition],
        updated: set[str],
    ) -> None:
        for v in serial_vars:
            if not v.regex_pattern:
                continue
            val = parse_regex_value(line, v.regex_pattern, v.regex_group)
            if val is not None:
                self._values[v.name] = val
                updated.add(v.name)

    def _evaluate_transforms(self, updated: set[str]) -> None:
        """Evaluate all transform variables using current values snapshot.

        Uses the latest value for each variable regardless of source (Serial, MQTT).
        Transforms are recomputed whenever any variable value changes, so mixed
        Serial/MQTT formulas always use the most recent value of each input.
        """
        transform_vars = [v for v in self._variables if v.source == "transform"]
        for v in transform_vars:
            if not v.expression:
                continue
            try:
                result = safe_eval(v.expression, dict(self._values))
                numeric = float(result)
                self._values[v.name] = numeric
                updated.add(v.name)
            except Exception:
                pass
