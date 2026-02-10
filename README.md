# nibterm

PySide6 serial terminal for IoT devices with logging, plotting, and command presets. I vibe-coded this as a test and because i
was not happy with existing terminal applications for my IoT work. 

<p align="center">
  <img src="static/terminal.png" alt="Terminal" width="400" style="display:inline-block;vertical-align:top;margin-right:10px;">
  <img src="static/dashboard.png" alt="Dashboard" width="400" style="display:inline-block;vertical-align:top;">
</p>


## Features

- Serial connection with configurable port settings
- Local echo, send-on-enter, auto reconnect, timestamp prefix
- Terminal theming (font and colors)
- Log incoming data to file
- Real-time plotting via pyqtgraph (CSV-like lines)
- YAML command presets with configurable parameters that render as buttons in the UI

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync
```

## Run

```bash
uv run nibterm
```

## Usage

- Open **View → Data Pipeline** to set delimiter, column names, and transformations.
- Use the **Connection** toolbar button to connect/disconnect a serial port.
- Send commands from the input field or load a YAML preset from **File → Load preset...**.
- Switch to the **Dashboard** tab to add plots and use **Setup** per plot.
- Start logging from **Tools → Start logging...**.

## Command preset example (YAML)

```yaml
# Preset for vmm-iot-owlogger
name: vmm-iot-owlogger
commands:
  - label: Reset
    command: "rst\n"
    color: "#ffe0b2"
  - label: Temp
    command: "temp\n"
  - label: Status
    command: "status\n"
    color: "#e3f2fd"
  - label: Set PWM
    command: "pwm {duty} {freq}\n"
    params:
      - name: duty
        label: Duty (%)
        default: "50"
      - name: freq
        label: Frequency (Hz)
        default: "1000"
```
