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
            lines as <b>CSV</b> or <b>JSON</b> and extract variables for plotting.</p>
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
            </ul>
            <h2>Adding Serial variables</h2>
            <p>On the <b>Terminal</b> tab, expand <b>Plot variables</b> below the command bar:</p>
            <ul>
                <li><b>CSV</b> — The last serial line is shown; click a column to add it as a variable (col0, col1, …).</li>
                <li><b>JSON</b> — The last valid JSON line is shown (pretty-printed). Click a value to add it as a variable with that JSON path.</li>
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
            <p>Command presets let you load a set of labeled commands (e.g. for a specific device) and run them from the
            <b>Commands</b> toolbar on the right. Each preset has a <b>name</b> and a list of <b>commands</b>. You can
            load a preset via the toolbar or <b>Serial</b> (or Commands) menu.</p>
            <h2>Preset and command descriptions</h2>
            <p>The preset is identified by its <b>name</b> in the YAML. Each command can have a <b>description</b>;
            it is shown as a tooltip on the command button in the toolbar.</p>
            <h2>YAML format</h2>
            <p>Presets are YAML files with this structure:</p>
            <ul>
                <li><b>name</b> — Preset name (string, required).</li>
                <li><b>commands</b> — List of command entries (required).</li>
            </ul>
            <p>Each command entry can have:</p>
            <ul>
                <li><b>label</b> — Button label in the toolbar (required).</li>
                <li><b>command</b> — The command string sent when you click the button (required). It can contain
                placeholders like <code>{param_name}</code> that are filled from the parameter inputs.</li>
                <li><b>color</b> — Optional button background color (e.g. <code>#e3f2fd</code>).</li>
                <li><b>description</b> — Optional tooltip for the command button.</li>
                <li><b>params</b> — Optional list of parameters. Each param has: <b>name</b> (used in the command template),
                optional <b>label</b>, <b>default</b>, and <b>description</b>. The UI shows a line edit per param; values
                are substituted into the command string.</li>
                <li><b>options</b> — Optional list of flags. Each option has: <b>flag</b> (e.g. <code>-s</code> or
                <code>--timeout</code>), optional <b>label</b>, <b>type</b> (<code>bool</code> or <code>value</code>),
                optional <b>default</b>, and optional <b>description</b>. In the UI, boolean options are checkboxes;
                value options are a checkbox plus a value field. When you run the command, only enabled options are
                appended (e.g. <code>read -s</code> or <code>read --timeout 5</code>).</li>
            </ul>
            <h3>Example YAML</h3>
            <pre>name: my-device
commands:
  - label: ping
    command: "ping\\n"
    description: Connectivity check.
  - label: read
    command: "read\\n"
    description: Read with optional submit.
    options:
      - flag: "-s"
        label: Submit
        type: bool
        default: false
  - label: set pwm
    command: "pwm {duty} {freq}\\n"
    params:
      - name: duty
        label: Duty (%)
        default: "50"
      - name: freq
        label: Freq (Hz)
        default: "1000"</pre>
            <p>In the YAML file, <code>\\n</code> in the command string sends a newline after the command.</p>
            <p>Parameter and option values are remembered per preset in the application settings.</p>
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
