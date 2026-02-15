"""JSON path extraction, pretty-printing, and variable-name helpers.

These are pure utility functions with no UI dependency.  They are
used by the MQTT monitor to parse JSON payloads and name variables.
"""
from __future__ import annotations

import json
import re

from jsonpath_ng import parse as jsonpath_parse
from jsonpath_ng.exceptions import JsonPathParserError


def build_json_with_path_ranges(
    obj: object, path: str = "$", indent: int = 0
) -> tuple[str, list[tuple[int, int, str, str]]]:
    """Build pretty-printed JSON and a list of ``(start, end, json_path, key_name)`` for each primitive value."""
    positions: list[tuple[int, int, str, str]] = []
    chunks: list[str] = []

    def tell() -> int:
        return sum(len(c) for c in chunks)

    def _key_from_path(p: str) -> str:
        if p == "$":
            return ""
        if "." in p:
            rest = p.split(".")[-1]
        else:
            rest = p.lstrip("$.")
        # e.g. "sensors[0]" -> "sensors_0", "value" -> "value"
        rest = re.sub(r"\[\s*(\d+)\s*\]", r"_\1", rest)
        return rest or "value"

    def emit(obj: object, path: str, key_name: str) -> None:
        start = tell()
        if obj is None:
            chunks.append("null")
        elif isinstance(obj, bool):
            chunks.append("true" if obj else "false")
        elif isinstance(obj, (int, float)):
            chunks.append(json.dumps(obj))
        elif isinstance(obj, str):
            chunks.append(json.dumps(obj))
        else:
            return
        end = tell()
        positions.append((start, end, path, key_name or _key_from_path(path)))

    def walk(obj: object, path: str, indent_level: int) -> None:
        key_name = _key_from_path(path)
        if obj is None or isinstance(obj, (bool, int, float, str)):
            emit(obj, path, key_name)
            return
        if isinstance(obj, dict):
            chunks.append("{\n")
            for i, (k, v) in enumerate(obj.items()):
                sub_path = f"{path}.{k}" if path != "$" else f"$.{k}"
                chunks.append(" " * (indent_level + 2))
                chunks.append(json.dumps(k) + ": ")
                walk(v, sub_path, indent_level + 2)
                if i < len(obj) - 1:
                    chunks.append(",")
                chunks.append("\n")
            chunks.append(" " * indent_level + "}")
            return
        if isinstance(obj, list):
            chunks.append("[\n")
            for i, v in enumerate(obj):
                sub_path = f"{path}[{i}]"
                chunks.append(" " * (indent_level + 2))
                walk(v, sub_path, indent_level + 2)
                if i < len(obj) - 1:
                    chunks.append(",")
                chunks.append("\n")
            chunks.append(" " * indent_level + "]")
            return

    walk(obj, path, indent)
    return "".join(chunks), positions


def extract_json_value(data: object, path_str: str) -> float | None:
    """Use a JSONPath expression to pull a numeric value out of *data*."""
    try:
        path = jsonpath_parse(path_str)
        matches = path.find(data)
        if not matches:
            return None
        val = matches[0].value
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                return None
        return None
    except JsonPathParserError:
        return None


def sanitize_var_name(name: str) -> str:
    """Make a string safe for use as a variable / column name."""
    if not name:
        return "value"
    s = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return s.strip("_") or "value"


def unique_variable_name(base: str, existing: set[str]) -> str:
    """Return *base* or ``base_2``, ``base_3``, … so the result is not in *existing*."""
    if not base:
        base = "value"
    if base not in existing:
        return base
    n = 2
    while f"{base}_{n}" in existing:
        n += 1
    return f"{base}_{n}"
