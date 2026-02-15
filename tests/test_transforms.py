"""Tests for nibterm.data.transforms."""
from __future__ import annotations

import math

import pytest

from nibterm.data.transforms import safe_eval


class TestSafeEval:
    def test_simple_addition(self) -> None:
        assert safe_eval("1 + 2", {}) == 3

    def test_variable_reference(self) -> None:
        assert safe_eval("x * 2", {"x": 5.0}) == 10.0

    def test_math_functions(self) -> None:
        result = safe_eval("sqrt(16)", {})
        assert result == 4.0

    def test_pi_constant(self) -> None:
        result = safe_eval("pi", {})
        assert result == pytest.approx(math.pi)

    def test_complex_expression(self) -> None:
        result = safe_eval("sin(x) + cos(y)", {"x": 0.0, "y": 0.0})
        assert result == pytest.approx(1.0)

    def test_power_operator(self) -> None:
        assert safe_eval("2 ** 3", {}) == 8.0

    def test_unsupported_import(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            safe_eval("__import__('os')", {})

    def test_unsupported_function(self) -> None:
        with pytest.raises(ValueError, match="Unsupported function"):
            safe_eval("eval('1')", {})
