"""Tests for nibterm.data.variable_manager."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from nibterm.config.variable import SerialParserConfig, VariableDefinition


class TestVariableManagerCSV:
    """Test CSV serial parsing via VariableManager."""

    def _make_manager(self, variables, serial_config=None):
        """Create a VariableManager with mocked QSettings."""
        from nibterm.data.variable_manager import VariableManager

        settings = MagicMock()
        settings.value = MagicMock(return_value=0)

        with patch("nibterm.data.variable_manager.load_variables", return_value=list(variables)):
            with patch("nibterm.data.variable_manager.SerialParserConfig.from_qsettings",
                       return_value=serial_config or SerialParserConfig(mode="csv", csv_delimiter=",")):
                mgr = VariableManager(settings)
        return mgr

    def test_csv_parse_basic(self) -> None:
        variables = [
            VariableDefinition(name="temp", source="serial", csv_column=0),
            VariableDefinition(name="hum", source="serial", csv_column=1),
        ]
        mgr = self._make_manager(variables)
        values, updated = mgr.process_serial_line("23.5,65.0")
        assert values["temp"] == pytest.approx(23.5)
        assert values["hum"] == pytest.approx(65.0)
        assert "temp" in updated
        assert "hum" in updated

    def test_csv_parse_semicolon(self) -> None:
        variables = [
            VariableDefinition(name="a", source="serial", csv_column=0),
            VariableDefinition(name="b", source="serial", csv_column=2),
        ]
        config = SerialParserConfig(mode="csv", csv_delimiter=";")
        mgr = self._make_manager(variables, config)
        values, updated = mgr.process_serial_line("1.0;skip;3.0")
        assert values["a"] == pytest.approx(1.0)
        assert values["b"] == pytest.approx(3.0)

    def test_csv_invalid_value_skipped(self) -> None:
        variables = [
            VariableDefinition(name="x", source="serial", csv_column=0),
        ]
        mgr = self._make_manager(variables)
        values, updated = mgr.process_serial_line("not_a_number")
        assert "x" not in updated

    def test_csv_column_out_of_range(self) -> None:
        variables = [
            VariableDefinition(name="x", source="serial", csv_column=5),
        ]
        mgr = self._make_manager(variables)
        values, updated = mgr.process_serial_line("1.0,2.0")
        assert "x" not in updated


class TestVariableManagerJSON:
    """Test JSON serial parsing."""

    def _make_manager(self, variables):
        from nibterm.data.variable_manager import VariableManager

        settings = MagicMock()
        settings.value = MagicMock(return_value=0)
        config = SerialParserConfig(mode="json")

        with patch("nibterm.data.variable_manager.load_variables", return_value=list(variables)):
            with patch("nibterm.data.variable_manager.SerialParserConfig.from_qsettings",
                       return_value=config):
                mgr = VariableManager(settings)
        return mgr

    def test_json_parse(self) -> None:
        variables = [
            VariableDefinition(name="temp", source="serial", json_path="$.temperature"),
        ]
        mgr = self._make_manager(variables)
        values, updated = mgr.process_serial_line('{"temperature": 22.5}')
        assert values["temp"] == pytest.approx(22.5)
        assert "temp" in updated

    def test_json_invalid_line(self) -> None:
        variables = [
            VariableDefinition(name="temp", source="serial", json_path="$.temperature"),
        ]
        mgr = self._make_manager(variables)
        values, updated = mgr.process_serial_line("not json")
        assert "temp" not in updated


class TestVariableManagerRegex:
    """Test regex serial parsing."""

    def _make_manager(self, variables):
        from nibterm.data.variable_manager import VariableManager

        settings = MagicMock()
        settings.value = MagicMock(return_value=0)
        config = SerialParserConfig(mode="regex")

        with patch("nibterm.data.variable_manager.load_variables", return_value=list(variables)):
            with patch("nibterm.data.variable_manager.SerialParserConfig.from_qsettings",
                       return_value=config):
                mgr = VariableManager(settings)
        return mgr

    def test_regex_parse(self) -> None:
        variables = [
            VariableDefinition(
                name="temp",
                source="serial",
                regex_pattern=r"temp=(\d+\.\d+)",
                regex_group=1,
            ),
        ]
        mgr = self._make_manager(variables)
        values, updated = mgr.process_serial_line("status: temp=23.5 ok")
        assert values["temp"] == pytest.approx(23.5)
        assert "temp" in updated

    def test_regex_no_match(self) -> None:
        variables = [
            VariableDefinition(
                name="temp",
                source="serial",
                regex_pattern=r"temp=(\d+\.\d+)",
                regex_group=1,
            ),
        ]
        mgr = self._make_manager(variables)
        values, updated = mgr.process_serial_line("no match here")
        assert "temp" not in updated


class TestVariableManagerMQTT:
    """Test MQTT value processing."""

    def _make_manager(self, variables):
        from nibterm.data.variable_manager import VariableManager

        settings = MagicMock()
        settings.value = MagicMock(return_value=0)

        with patch("nibterm.data.variable_manager.load_variables", return_value=list(variables)):
            with patch("nibterm.data.variable_manager.SerialParserConfig.from_qsettings",
                       return_value=SerialParserConfig()):
                mgr = VariableManager(settings)
        return mgr

    def test_mqtt_process(self) -> None:
        variables = [
            VariableDefinition(name="sensor_temp", source="mqtt", mqtt_topic="room/1", json_path="$.temp"),
        ]
        mgr = self._make_manager(variables)
        values, updated = mgr.process_mqtt_values({"sensor_temp": 25.0})
        assert values["sensor_temp"] == pytest.approx(25.0)
        assert "sensor_temp" in updated


class TestVariableManagerTransforms:
    """Test transform evaluation."""

    def _make_manager(self, variables):
        from nibterm.data.variable_manager import VariableManager

        settings = MagicMock()
        settings.value = MagicMock(return_value=0)

        with patch("nibterm.data.variable_manager.load_variables", return_value=list(variables)):
            with patch("nibterm.data.variable_manager.SerialParserConfig.from_qsettings",
                       return_value=SerialParserConfig()):
                mgr = VariableManager(settings)
        return mgr

    def test_transform_after_serial(self) -> None:
        variables = [
            VariableDefinition(name="raw", source="serial", csv_column=0),
            VariableDefinition(name="scaled", source="transform", expression="raw * 0.01"),
        ]
        mgr = self._make_manager(variables)
        values, updated = mgr.process_serial_line("500")
        assert values["scaled"] == pytest.approx(5.0)
        assert "scaled" in updated

    def test_transform_after_mqtt(self) -> None:
        variables = [
            VariableDefinition(name="x", source="mqtt"),
            VariableDefinition(name="doubled", source="transform", expression="x * 2"),
        ]
        mgr = self._make_manager(variables)
        values, updated = mgr.process_mqtt_values({"x": 7.0})
        assert values["doubled"] == pytest.approx(14.0)
        assert "doubled" in updated
