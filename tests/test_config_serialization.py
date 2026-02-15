"""Tests for nibterm.config.plot_config serialization helpers."""
from __future__ import annotations

from nibterm.config.plot_config import (
    parse_string_list,
    serialize_string_list,
)


class TestStringList:
    def test_round_trip(self) -> None:
        values = ["alpha", "beta", "gamma"]
        text = serialize_string_list(values)
        assert parse_string_list(text) == values

    def test_empty(self) -> None:
        assert parse_string_list("") == []

    def test_empty_entries_filtered(self) -> None:
        assert serialize_string_list(["a", "", "b"]) == "a; b"
