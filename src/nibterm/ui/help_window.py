"""Help window with navigation and HTML content."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


def _help_content() -> list[tuple[str, str]]:
    """Return list of (section_title, html_content) for the help viewer."""
    return [
        (
            "Welcome",
            """
            <h1>nibterm Help</h1>
            <p>nibterm is a serial and MQTT terminal for IoT devices. You can capture data from serial ports
            and MQTT brokers, define variables (CSV columns, JSON paths, or computed transforms), and plot them
            on the Dashboard.</p>
            <h2>Main tabs</h2>
            <ul>
                <li><b>Terminal</b> — Serial console, command input, and Serial plot variables panel.</li>
                <li><b>MQTT</b> — Topic browser, message view, and MQTT plot variables table.</li>
                <li><b>Dashboard</b> — Plots of your variables over time (or XY plots).</li>
            </ul>
            <p>Use the left navigation to jump to detailed sections.</p>
            """,
        ),
        (
            "Serial interface",
            """
            <h1>Serial interface</h1>
            <p>Connect to a serial port (e.g. USB-UART) to send and receive text. The app can parse incoming
            lines as <b>CSV</b>, <b>JSON</b>, or <b>Regex</b> and extract variables for plotting.</p>
            <h2>Connecting</h2>
            <ul>
                <li>Use <b>Serial → Connect</b> (or the connection toolbar) to open the port.</li>
                <li>Configure port, baud rate, and other options in <b>Serial → Settings</b>.</li>
            </ul>
            <h2>Parser mode</h2>
            <p>In <b>Serial → Parser</b> you choose:</p>
            <ul>
                <li><b>CSV</b> — Comma-separated (or custom delimiter) columns. Set the delimiter if needed.</li>
                <li><b>JSON</b> — Each line is parsed as JSON. You can set an optional <b>JSON prefix</b> (e.g. <code>Payload: </code>)
                so lines like <code>Payload: {"temp": 25.3}</code> are stripped and parsed correctly.</li>
                <li><b>Regex</b> — Each variable gets its own Python regex pattern and capture group.
                Use this when lines have a fixed but irregular format (see the <i>Regex parser</i> section for details).</li>
            </ul>
            <h2>Adding Serial variables</h2>
            <p>On the <b>Terminal</b> tab, expand <b>Plot variables</b> below the command bar:</p>
            <ul>
                <li><b>CSV</b> — The last serial line is shown; click a column to add it as a variable (col0, col1, …).</li>
                <li><b>JSON</b> — The last valid JSON line is shown (pretty-printed). Click a value to add it as a variable with that JSON path.</li>
                <li><b>Regex</b> — Click <b>Add</b> to open the <i>Configure regex extraction</i> dialog. Enter your pattern,
                choose a capture group, and confirm. Double-click an existing row to edit its pattern.</li>
            </ul>
            <p>You can also use <b>Add</b> / <b>Remove</b> / <b>Clear all</b> in that panel. Variable names can be edited in the table;
            rename in the Variables dialog (Manage variables) or in the Serial plot variables table.</p>
            """,
        ),
        (
            "MQTT interface",
            """
            <h1>MQTT interface</h1>
            <p>Connect to an MQTT broker to subscribe to topics and receive messages. Each topic can be parsed
            as <b>JSON</b> or <b>CSV</b>; you add variables by clicking values or columns in the message view.</p>
            <h2>Connecting</h2>
            <ul>
                <li>Configure broker and credentials in <b>MQTT → Settings</b>.</li>
                <li>Use the connection toolbar or <b>MQTT → Connect</b> to connect.</li>
            </ul>
            <h2>Topics and parsing</h2>
            <p>On the <b>MQTT</b> tab you see a topic tree. Select a topic to view its last message. Above the message:</p>
            <ul>
                <li>Choose <b>Parse this topic as: JSON</b> or <b>CSV</b> (and set delimiter for CSV).</li>
            </ul>
            <p>The message area shows the last payload. Click a JSON value or CSV column to add it as a plot variable
            for that topic. The table below lists MQTT variables (topic, extraction, name).</p>
            <h2>Multiple topics</h2>
            <p>You can add variables from different topics. Each variable is tied to one topic and one extraction
            (JSON path or CSV column). Transforms can combine Serial and MQTT variables.</p>
            """,
        ),
        (
            "Regex parser",
            """
            <h1>Regex parser</h1>
            <p>The <b>Regex</b> parser lets each variable define its own Python regular expression to extract
            a numeric value from any incoming serial line. This is ideal for devices that send human-readable
            or mixed-format lines where CSV and JSON do not apply.</p>

            <h2>How it works</h2>
            <p>For each variable you define a <b>pattern</b> and a <b>capture group</b> number:</p>
            <ul>
                <li>The pattern is searched across the entire line with <code>re.search()</code> — it does not have to match from the start.</li>
                <li>The <b>capture group</b> selects which part of the match to extract:
                    <ul>
                        <li><b>0</b> — the entire match (useful when the pattern itself is the value).</li>
                        <li><b>1, 2, …</b> — the corresponding <code>(…)</code> group in your pattern.</li>
                    </ul>
                </li>
                <li>The extracted text is converted to a <code>float</code>. If the line does not match, or the
                value is not numeric, the variable keeps its previous value.</li>
            </ul>

            <h2>Configuring a variable</h2>
            <p>Click <b>Add</b> in the <i>Plot variables</i> panel (with Regex mode active) to open the
            <b>Configure regex extraction</b> dialog:</p>
            <ul>
                <li><b>Test line</b> — pre-filled with the last received serial line. You can also type or paste
                any sample line to try patterns before committing.</li>
                <li><b>Pattern</b> — your Python regex. The dialog shows a live preview as you type.</li>
                <li><b>Capture group</b> — spin box selecting which group to read (0 = entire match).</li>
                <li><b>Extracted value</b> — live feedback: green = numeric value found, orange = match found but
                not numeric, red = no match or invalid pattern.</li>
            </ul>
            <p>Double-click an existing regex variable row to reopen the dialog and edit its pattern.</p>

            <h2>Examples</h2>

            <h3>Simple text-string matching (presence / state)</h3>
            <p>Line: <code>STATUS: OK  uptime=1234</code></p>
            <p>To detect whether <code>OK</code> appears and turn it into a 1:</p>
            <pre>Pattern: OK
Capture group: 0   →  extracted text "OK" (not numeric — use a group instead)</pre>
            <p>Better approach — wrap a digit that signals the state:</p>
            <pre>Line:    STATUS: OK  uptime=1234
Pattern: uptime=([0-9]+)
Group:   1   →  1234.0</pre>
            <p>Or match a keyword and map it via a transform (e.g. variable <code>ok_raw</code> always = 1
            when the line matches, else no update — useful as a heartbeat):</p>
            <pre>Pattern: (OK)
Group:   0   →  no numeric output (orange warning in the dialog)
Use group 1 of a numeric suffix instead, e.g.:
Pattern: OK\s+uptime=(\d+)
Group:   1   →  1234.0</pre>

            <h3>Extracting a single number after a label</h3>
            <p>Line: <code>temp: 23.7 hum: 58.1</code></p>
            <pre>Variable "temperature":
  Pattern: temp:\s*([\d.]+)
  Group:   1   →  23.7

Variable "humidity":
  Pattern: hum:\s*([\d.]+)
  Group:   1   →  58.1</pre>

            <h3>Extracting a number with a sign or scientific notation</h3>
            <p>Line: <code>accel=-0.981 gyro=1.23e-4</code></p>
            <pre>Variable "accel":
  Pattern: accel=([+-]?[\d.]+)
  Group:   1   →  -0.981

Variable "gyro":
  Pattern: gyro=([+-]?[\d.eE+-]+)
  Group:   1   →  1.23e-4  →  0.000123</pre>

            <h3>Matching anywhere in a noisy line</h3>
            <p>Line: <code>[DBG] sensor#3 val=42 ok</code></p>
            <pre>Pattern: val=(\d+)
Group:   1   →  42.0
(re.search finds the match even with surrounding noise)</pre>

            <h3>Using group 0 (entire match is the number)</h3>
            <p>Line: <code>1013.25</code> (bare number, nothing else)</p>
            <pre>Pattern: [\d.]+
Group:   0   →  1013.25</pre>

            <h2>Tips</h2>
            <ul>
                <li>Use <code>[\d.]+</code> for simple decimals, <code>[+-]?[\d.eE+-]+</code> for signed/scientific.</li>
                <li>Always put the number part in a capture group (<code>(…)</code>) and set group ≥ 1 to avoid
                accidentally matching label text.</li>
                <li>Each variable has its own independent pattern — you can mix CSV/JSON-sourced variables
                with Regex variables via <b>Transforms</b>.</li>
                <li>The test line in the dialog is editable: paste a representative line from your device's
                actual output to verify your pattern before adding the variable.</li>
            </ul>
            """,
        ),
        (
            "Variables and parsers",
            """
            <h1>Variables and parsers</h1>
            <p>Variables are the named values you plot. They come from:</p>
            <ul>
                <li><b>Serial</b> — CSV column index or JSON path (set in Serial → Parser and added via the Serial Plot variables panel).</li>
                <li><b>MQTT</b> — Topic + JSON path or CSV column (added by clicking in the MQTT message view).</li>
                <li><b>Transform</b> — Formula from other variables (added in the Variables dialog).</li>
            </ul>
            <h2>Managing variables</h2>
            <p>Open <b>Variables → Manage variables</b> to:</p>
            <ul>
                <li>See all variables (Source, Source config, Name, Unit, Value).</li>
                <li><b>Edit</b> — Change name and unit only for Serial/MQTT; for transforms you can edit the expression.</li>
                <li><b>Remove</b> — Delete a variable. If a transform depends on it, that transform is removed too.</li>
                <li><b>Add transform</b> — Create a new variable from a formula (e.g. <code>col0 * 0.01</code>, <code>temp_c + 273.15</code>).</li>
            </ul>
            <p>Serial and MQTT variables are created in their respective tabs (Terminal and MQTT); the Variables dialog
            does not add new Serial/MQTT sources, only transforms and name/unit edits.</p>
            <h2>Unique names</h2>
            <p>Every variable must have a unique name. If you rename one to an existing name, the app will uniquify it
            (e.g. name_2). When you rename a variable, any transform expression that referenced its old name is updated
            automatically.</p>
            """,
        ),
        (
            "Transforms",
            """
            <h1>Transforms</h1>
            <p>Transform variables are computed from other variables using a formula. They update whenever any of their
            inputs change (Serial, MQTT, or other transforms).</p>
            <h2>Adding a transform</h2>
            <ul>
                <li>Open <b>Variables → Manage variables</b> and click <b>Add transform...</b></li>
                <li>Enter a <b>Name</b> (e.g. <code>temp_k</code>), optional <b>Unit</b> (e.g. <code>K</code>), and an <b>Expression</b>.</li>
                <li>The expression can use existing variable names and math: <code>+ - * / ** %</code>, <code>sin</code>, <code>cos</code>,
                <code>sqrt</code>, <code>log</code>, <code>exp</code>, <code>abs</code>, <code>min</code>, <code>max</code>, and constants
                <code>pi</code>, <code>e</code>.</li>
            </ul>
            <p>Example: <code>col0 * 0.01</code> (scale column 0), <code>temp_c + 273.15</code> (Celsius to Kelvin),
            <code>serial_a + mqtt_b</code> (mix Serial and MQTT). The dialog shows <b>Available:</b> with variable names you can use.</p>
            <h2>Mixed sources</h2>
            <p>Transforms use the <em>latest</em> value of each input. If one variable comes from Serial and another from MQTT
            (different update rates), the transform is recomputed whenever any of them updates; the plot always uses the
            most recent value for each.</p>
            """,
        ),
        (
            "Dashboard and plotting",
            """
            <h1>Dashboard and plotting</h1>
            <p>The <b>Dashboard</b> tab shows one or more plots. Each plot can display one or more variables over time
            (time series) or an XY plot (one variable vs another).</p>
            <h2>Adding a plot</h2>
            <ul>
                <li>Use <b>Dashboard → Add plot</b> (or the Dashboard menu) to create a new plot.</li>
                <li>Use <b>Setup plot...</b> to choose which variables to show and the plot type (time series or XY).</li>
            </ul>
            <h2>Transferring variables to a plot</h2>
            <ul>
                <li>Open <b>Setup plot...</b> for the active plot.</li>
                <li>Select variables from the list (all your defined variables appear there: Serial, MQTT, and Transforms).</li>
                <li>For time series: add variables to the series list; they will be plotted vs time.</li>
                <li>For XY: choose one variable for X and one for Y.</li>
            </ul>
            <p>Variables are fed to the Dashboard automatically as data arrives (Serial or MQTT). Transform values
            update when their inputs change, so they appear on the plot without extra steps.</p>
            <h2>Plot actions</h2>
            <p><b>Clear plot</b> clears the current data from the active plot. <b>Tile plots</b> / <b>Cascade plots</b>
            arrange multiple plot windows.</p>
            """,
        ),
        (
            "Command presets",
            """
            <h1>Command presets</h1>
            <p>Command presets let you load a set of labeled buttons (e.g. for a specific device) into the
            <b>Commands</b> toolbar on the right side of the Terminal tab. Each button sends a command string
            over the serial port when clicked. Presets are YAML files you load via <b>Serial → Load preset…</b>
            or the toolbar header button.</p>

            <h2>Top-level YAML structure</h2>
            <ul>
                <li><b>name</b> (string, required) — Displayed in the toolbar header.</li>
                <li><b>commands</b> (list, required) — One entry per button.</li>
            </ul>

            <h2>Command entry fields</h2>

            <h3>label <span style="font-weight:normal;color:gray">(string, required)</span></h3>
            <p>Text shown on the button in the toolbar. Keep it short.</p>

            <h3>command <span style="font-weight:normal;color:gray">(string, required)</span></h3>
            <p>The string sent over the serial port when the button is clicked. Use <code>\\n</code> to send
            a newline (most devices need one to terminate a command). Placeholders in curly braces
            (<code>{name}</code>) are filled in from <b>params</b> at runtime.</p>

            <h3>description <span style="font-weight:normal;color:gray">(string, optional)</span></h3>
            <p>Shown as a tooltip when you hover the button. Use it to describe what the command does,
            expected response, or any important notes.</p>

            <h3>color <span style="font-weight:normal;color:gray">(string, optional)</span></h3>
            <p>Background color for the button. Accepts any CSS color value: named colors (<code>lightblue</code>),
            hex (<code>#e3f2fd</code>), or RGB (<code>rgb(200,230,255)</code>). Useful for grouping related
            commands visually.</p>

            <h3>params <span style="font-weight:normal;color:gray">(list, optional)</span></h3>
            <p>Defines text-input fields that appear below the button. Each entry has:</p>
            <ul>
                <li><b>name</b> (required) — Identifier used as the placeholder in the command string
                (e.g. <code>name: duty</code> → placeholder <code>{duty}</code>).</li>
                <li><b>label</b> (optional) — Human-readable label shown next to the input field.
                Defaults to the <code>name</code> if omitted.</li>
                <li><b>default</b> (optional) — Pre-filled value when the preset is loaded.
                Always treated as a string; numeric values are coerced automatically.</li>
                <li><b>description</b> (optional) — Tooltip shown on the input field.</li>
            </ul>
            <p>When you click the button, each <code>{placeholder}</code> in the command string is replaced
            with the current content of its input field. If any required field is empty the button is
            disabled until a value is provided. Parameter values are remembered per preset across sessions.</p>

            <h3>options <span style="font-weight:normal;color:gray">(list, optional)</span></h3>
            <p>Defines toggleable flags appended to the command. Each entry has:</p>
            <ul>
                <li><b>flag</b> (required) — The flag text appended to the command when enabled
                (e.g. <code>-s</code>, <code>--verbose</code>).</li>
                <li><b>label</b> (optional) — Text next to the checkbox. Defaults to <code>flag</code>.</li>
                <li><b>type</b> (optional, <code>bool</code> or <code>value</code>) —
                    <ul>
                        <li><code>bool</code> (default) — A single checkbox. When checked, the flag is appended
                        as-is (e.g. <code>read -s</code>).</li>
                        <li><code>value</code> — A checkbox plus a text field. When checked, the flag and the
                        field value are appended (e.g. <code>read --timeout 5</code>).</li>
                    </ul>
                </li>
                <li><b>default</b> (optional) — For <code>bool</code>: <code>true</code>/<code>false</code>.
                For <code>value</code>: the default text in the value field.</li>
                <li><b>description</b> (optional) — Tooltip on the checkbox.</li>
            </ul>
            <p>Only <em>enabled</em> (checked) options are appended to the command. Options are appended
            in the order they are defined. If the command string ends with <code>\\n</code>, options are
            inserted before the trailing newline.</p>

            <h2>Complete example</h2>
            <pre>name: my-sensor-board
commands:

  # Simple ping — no parameters, just sends "ping" followed by newline
  - label: ping
    command: "ping\\n"
    color: "#e8f5e9"
    description: >
      Send a connectivity ping. Device replies "pong" if alive.

  # Read sensor — a bool flag controls whether the result is also stored
  - label: read sensor
    command: "read\\n"
    color: "#e3f2fd"
    description: Read latest sensor value. Use 'Submit' to persist it on the device.
    options:
      - flag: "-s"
        label: Submit (persist)
        type: bool
        default: false
        description: Append -s to store the reading in non-volatile memory.
      - flag: "--verbose"
        label: Verbose output
        type: bool
        default: false
        description: Request full diagnostic output.

  # Set LED brightness — a numeric parameter
  - label: set LED
    command: "led {brightness}\\n"
    color: "#fff9c4"
    description: Set LED brightness (0–255).
    params:
      - name: brightness
        label: Brightness (0-255)
        default: "128"
        description: Integer 0 (off) to 255 (full).

  # PWM control — two parameters and an optional frequency flag
  - label: set PWM
    command: "pwm {duty} {freq}\\n"
    description: Set PWM duty cycle and base frequency, with optional prescaler flag.
    params:
      - name: duty
        label: Duty cycle (%)
        default: "50"
        description: Duty cycle as a percentage (0–100).
      - name: freq
        label: Frequency (Hz)
        default: "1000"
        description: Base PWM frequency in Hz.
    options:
      - flag: "--prescaler"
        label: Prescaler
        type: value
        default: "8"
        description: >
          Clock prescaler value. When checked, '--prescaler N' is appended
          (e.g. 'pwm 50 1000 --prescaler 8').

  # Firmware update — danger color, value-type option for target address
  - label: flash
    command: "flash {file}\\n"
    color: "#ffccbc"
    description: Upload firmware file to the device.
    params:
      - name: file
        label: Firmware path
        default: "firmware.bin"
    options:
      - flag: "--addr"
        label: Start address
        type: value
        default: "0x08000000"
        description: Flash start address (hex). Omit to use device default.</pre>

            <p><b>Notes:</b></p>
            <ul>
                <li><code>\\n</code> in the command string sends a newline; most serial devices require it.</li>
                <li>Parameter and option values are saved per preset in application settings and restored
                the next time the preset is loaded.</li>
                <li>The toolbar width auto-adjusts to the longest button label in the preset.</li>
            </ul>
            """,
        ),
    ]


class HelpWindow(QDialog):
    """Modal or modeless dialog with section list and HTML content."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("nibterm Help")
        self.setMinimumSize(720, 520)
        self.resize(860, 580)

        self._sections = _help_content()
        self._list = QListWidget()
        self._list.setMaximumWidth(220)
        self._list.setMinimumWidth(180)
        for title, _ in self._sections:
            self._list.addItem(QListWidgetItem(title))
        self._list.currentRowChanged.connect(self._on_section_changed)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setHtml(self._sections[0][1] if self._sections else "")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._list)
        splitter.addWidget(self._browser)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 600])

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)

        self._list.setCurrentRow(0)

    def _on_section_changed(self, row: int) -> None:
        if 0 <= row < len(self._sections):
            self._browser.setHtml(self._sections[row][1])
            self._browser.scrollToAnchor("")
