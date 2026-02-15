"""PlotConfig dataclass and QSettings persistence.

After the unified-variables refactor, ``PlotConfig`` only carries
per-plot *display* configuration (mode, selected series, buffer, refresh
rate).  All variable definitions and parsing configuration live in
``config.variable`` and are managed by ``VariableManager``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QSettings

from . import defaults
from . import settings_keys as SK


@dataclass
class PlotConfig:
    mode: str = "timeseries"
    series_variables: list[str] = field(default_factory=list)
    xy_x_var: str = ""
    xy_y_var: str = ""
    buffer_size: int = defaults.DEFAULT_PLOT_BUFFER_SIZE
    update_ms: int = defaults.DEFAULT_PLOT_UPDATE_MS

    def to_qsettings(self, settings: QSettings) -> None:
        to_qsettings(self, settings)

    @staticmethod
    def from_qsettings(settings: QSettings) -> "PlotConfig":
        return from_qsettings(settings)


# ---------------------------------------------------------------------------
# Primitive (de-)serializers
# ---------------------------------------------------------------------------


def parse_string_list(text: str) -> list[str]:
    values: list[str] = []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if chunk:
            values.append(chunk)
    return values


def serialize_string_list(values: list[str]) -> str:
    return "; ".join(value for value in values if value)


# ---------------------------------------------------------------------------
# QSettings round-trip
# ---------------------------------------------------------------------------


def to_qsettings(config: PlotConfig, settings: QSettings) -> None:
    """Persist *config* into *settings*."""
    settings.setValue(SK.PLOT_MODE, config.mode)
    settings.setValue(SK.PLOT_SERIES_VARS, serialize_string_list(config.series_variables))
    settings.setValue(SK.PLOT_XY_X_VAR, config.xy_x_var)
    settings.setValue(SK.PLOT_XY_Y_VAR, config.xy_y_var)
    settings.setValue(SK.PLOT_BUFFER_SIZE, config.buffer_size)
    settings.setValue(SK.PLOT_UPDATE_MS, config.update_ms)


def from_qsettings(settings: QSettings) -> PlotConfig:
    """Restore a ``PlotConfig`` from *settings*."""
    series_vars = parse_string_list(settings.value(SK.PLOT_SERIES_VARS, "", str))
    xy_x_var = settings.value(SK.PLOT_XY_X_VAR, "", str)
    xy_y_var = settings.value(SK.PLOT_XY_Y_VAR, "", str)
    return PlotConfig(
        mode=settings.value(SK.PLOT_MODE, "timeseries", str),
        series_variables=series_vars,
        xy_x_var=xy_x_var,
        xy_y_var=xy_y_var,
        buffer_size=settings.value(SK.PLOT_BUFFER_SIZE, defaults.DEFAULT_PLOT_BUFFER_SIZE, int),
        update_ms=settings.value(SK.PLOT_UPDATE_MS, defaults.DEFAULT_PLOT_UPDATE_MS, int),
    )
