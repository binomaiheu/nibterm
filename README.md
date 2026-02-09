# nibterm

PySide6 serial terminal for IoT devices with logging, plotting, and command presets.

## Features

- Serial connection with configurable port settings
- Local echo, send-on-enter, auto reconnect, timestamp prefix
- Terminal theming (font and colors)
- Log incoming data to file
- Real-time plotting via pyqtgraph (CSV-like lines)
- YAML command presets that render buttons in the UI

## Requirements

- Python 3.8+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

## Run

```bash
uv run nibterm
```

## Command preset example (YAML)

```yaml
# Preset for ESP32 device
name: ESP32
commands:
  - label: Reset
    command: "rst\n"
  - label: Temp
    command: "temp\n"
```
