"""Shared parsing for Serial and MQTT: CSV, JSON, regex.

Used by VariableManager and MQTT value extraction so both sources
use the same logic.
"""
from __future__ import annotations

import json
import re


def parse_csv_line(
    line: str,
    delimiter: str,
    column_indices: list[int] | None = None,
) -> dict[int, float]:
    """Split line by delimiter and return map column_index -> float.

    If column_indices is None, use all indices 0..len(parts)-1 that
    parse as float. Only successful float conversions are included.
    """
    parts = [p.strip() for p in line.split(delimiter)]
    result: dict[int, float] = {}
    indices = column_indices if column_indices is not None else range(len(parts))
    for i in indices:
        if i < 0 or i >= len(parts):
            continue
        try:
            result[i] = float(parts[i])
        except (ValueError, TypeError):
            pass
    return result


def parse_json_payload(payload: str) -> object | None:
    """Parse a JSON payload string. Returns None on error."""
    try:
        return json.loads(payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def parse_regex_value(line: str, pattern: str, group: int) -> float | None:
    """Extract one capture group from line and return as float, or None."""
    try:
        m = re.search(pattern, line)
    except re.error:
        return None
    if m is None:
        return None
    try:
        raw = m.group(group)
        return float(raw)
    except (IndexError, ValueError, TypeError):
        return None
