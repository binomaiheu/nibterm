"""Centralised QSettings key constants.

Using named constants instead of string literals prevents typos and
makes bulk-renaming trivial.
"""

# -- window ----------------------------------------------------------------
WINDOW_GEOMETRY = "window/geometry"
WINDOW_STATE = "window/state"

# -- serial ----------------------------------------------------------------
SERIAL_PORT_NAME = "serial/port_name"
SERIAL_BAUD_RATE = "serial/baud_rate"
SERIAL_DATA_BITS = "serial/data_bits"
SERIAL_PARITY = "serial/parity"
SERIAL_STOP_BITS = "serial/stop_bits"
SERIAL_FLOW_CONTROL = "serial/flow_control"
SERIAL_LOCAL_ECHO = "serial/local_echo"
SERIAL_SEND_ON_ENTER = "serial/send_on_enter"
SERIAL_LINE_ENDING = "serial/line_ending"
SERIAL_AUTO_RECONNECT = "serial/auto_reconnect"
SERIAL_TIMESTAMP_PREFIX = "serial/timestamp_prefix"

# -- appearance ------------------------------------------------------------
APPEARANCE_FONT_FAMILY = "appearance/font_family"
APPEARANCE_FONT_SIZE = "appearance/font_size"
APPEARANCE_BACKGROUND_COLOR = "appearance/background_color"
APPEARANCE_TEXT_COLOR = "appearance/text_color"

# -- plot ------------------------------------------------------------------
PLOT_DELIMITER = "plot/delimiter"
PLOT_MODE = "plot/mode"
PLOT_COLUMNS = "plot/columns"
PLOT_X_COLUMN = "plot/x_column"
PLOT_Y_COLUMN = "plot/y_column"
PLOT_COLUMN_NAMES = "plot/column_names"
PLOT_MQTT_COLUMN_INDICES = "plot/mqtt_column_indices"
PLOT_TRANSFORM = "plot/transform"
PLOT_SERIES_VARS = "plot/series_vars"
PLOT_XY_X_VAR = "plot/xy_x_var"
PLOT_XY_Y_VAR = "plot/xy_y_var"
PLOT_BUFFER_SIZE = "plot/buffer_size"
PLOT_UPDATE_MS = "plot/update_ms"

# -- mqtt ------------------------------------------------------------------
MQTT_HOST = "mqtt/host"
MQTT_PORT = "mqtt/port"
MQTT_USERNAME = "mqtt/username"
MQTT_PASSWORD = "mqtt/password"
MQTT_USE_TLS = "mqtt/use_tls"
MQTT_CA_CERTIFICATE = "mqtt/ca_certificate"
MQTT_TLS_INSECURE = "mqtt/tls_insecure"
MQTT_TOPIC_ROOT = "mqtt/topic_root"
MQTT_PLOT_VAR_COUNT = "mqtt/plot_var_count"
MQTT_PLOT_VAR_TOPIC = "mqtt/plot_var_topic_{}"  # format with index
MQTT_PLOT_VAR_PATH = "mqtt/plot_var_path_{}"
MQTT_PLOT_VAR_NAME = "mqtt/plot_var_name_{}"
MQTT_TOPIC_PARSERS = "mqtt/topic_parsers"  # JSON: topic -> {mode, csv_delimiter}

# -- dashboard -------------------------------------------------------------
DASHBOARD_PLOT_COUNT = "dashboard/plot_count"
DASHBOARD_PLOTS_PREFIX = "dashboard/plots/{}"  # format with index

# -- variables (unified) ---------------------------------------------------
VAR_COUNT = "variables/count"
VAR_PREFIX = "variables/{}"  # format with index
SERIAL_PARSER_MODE = "serial_parser/mode"
SERIAL_PARSER_CSV_DELIMITER = "serial_parser/csv_delimiter"
SERIAL_PARSER_JSON_PREFIX = "serial_parser/json_prefix"

# -- commands --------------------------------------------------------------
COMMANDS_LAST_PATH = "commands/last_path"
COMMANDS_PARAMS_PREFIX = "commands/params/{preset}/{label}/{param}"
