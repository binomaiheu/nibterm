"""Tests for nibterm.data.json_utils."""
from __future__ import annotations

from nibterm.data.json_utils import (
    build_json_with_path_ranges,
    extract_json_value,
    sanitize_var_name,
    unique_variable_name,
)


class TestBuildJsonWithPathRanges:
    def test_flat_object(self) -> None:
        obj = {"a": 1, "b": "hello"}
        text, ranges = build_json_with_path_ranges(obj)
        assert "1" in text
        assert '"hello"' in text
        # Should have two primitive value ranges
        assert len(ranges) == 2
        # Each range is (start, end, json_path, key_name)
        paths = {r[2] for r in ranges}
        assert "$.a" in paths
        assert "$.b" in paths

    def test_nested_object(self) -> None:
        obj = {"outer": {"inner": 42}}
        text, ranges = build_json_with_path_ranges(obj)
        assert "42" in text
        assert len(ranges) == 1
        assert ranges[0][2] == "$.outer.inner"

    def test_list_values(self) -> None:
        obj = [10, 20, 30]
        text, ranges = build_json_with_path_ranges(obj)
        assert len(ranges) == 3
        paths = [r[2] for r in ranges]
        assert paths == ["$[0]", "$[1]", "$[2]"]

    def test_null_and_bool(self) -> None:
        obj = {"flag": True, "empty": None}
        text, ranges = build_json_with_path_ranges(obj)
        assert "true" in text
        assert "null" in text
        assert len(ranges) == 2

    def test_empty_object(self) -> None:
        obj = {}
        text, ranges = build_json_with_path_ranges(obj)
        assert ranges == []
        assert "{" in text


class TestExtractJsonValue:
    def test_simple_path(self) -> None:
        data = {"temperature": 22.5}
        assert extract_json_value(data, "$.temperature") == 22.5

    def test_nested_path(self) -> None:
        data = {"sensor": {"value": 100}}
        assert extract_json_value(data, "$.sensor.value") == 100.0

    def test_missing_path(self) -> None:
        data = {"a": 1}
        assert extract_json_value(data, "$.nonexistent") is None

    def test_string_numeric(self) -> None:
        data = {"val": "3.14"}
        assert extract_json_value(data, "$.val") == 3.14

    def test_string_non_numeric(self) -> None:
        data = {"val": "hello"}
        assert extract_json_value(data, "$.val") is None

    def test_invalid_path(self) -> None:
        data = {"a": 1}
        assert extract_json_value(data, "$$invalid[") is None

    def test_array_index(self) -> None:
        data = {"values": [10, 20, 30]}
        assert extract_json_value(data, "$.values[1]") == 20.0


class TestSanitizeVarName:
    def test_normal_name(self) -> None:
        assert sanitize_var_name("temperature") == "temperature"

    def test_special_chars(self) -> None:
        assert sanitize_var_name("my-var!@#") == "my_var"

    def test_empty(self) -> None:
        assert sanitize_var_name("") == "value"

    def test_only_underscores(self) -> None:
        assert sanitize_var_name("___") == "value"

    def test_spaces(self) -> None:
        assert sanitize_var_name(" hello world ") == "hello_world"


class TestUniqueVariableName:
    def test_no_conflict(self) -> None:
        assert unique_variable_name("temp", set()) == "temp"

    def test_conflict(self) -> None:
        assert unique_variable_name("temp", {"temp"}) == "temp_2"

    def test_multiple_conflicts(self) -> None:
        assert unique_variable_name("x", {"x", "x_2", "x_3"}) == "x_4"

    def test_empty_base(self) -> None:
        assert unique_variable_name("", set()) == "value"
