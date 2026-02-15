from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..mqtt.settings import MQTTSettings


class MQTTSettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("MQTT broker")

        form = QFormLayout()
        self._host = QLineEdit()
        self._host.setPlaceholderText("localhost")
        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(1883)
        self._username = QLineEdit()
        self._username.setPlaceholderText("Optional")
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Optional")
        self._use_tls = QCheckBox("Use TLS")
        self._ca_cert = QLineEdit()
        self._ca_cert.setPlaceholderText("Path to CA certificate (optional)")
        self._ca_cert_browse = QPushButton("Browse…")
        self._ca_cert_browse.clicked.connect(self._browse_ca_cert)
        ca_row = QHBoxLayout()
        ca_row.addWidget(self._ca_cert)
        ca_row.addWidget(self._ca_cert_browse)
        self._tls_insecure = QCheckBox("Skip server certificate verification (insecure)")
        self._topic_root = QLineEdit()
        self._topic_root.setPlaceholderText("e.g. sensors or leave empty for #")

        form.addRow("Host", self._host)
        form.addRow("Port", self._port)
        form.addRow("Username", self._username)
        form.addRow("Password", self._password)
        form.addRow("", self._use_tls)
        form.addRow("CA certificate", ca_row)
        form.addRow("", self._tls_insecure)
        form.addRow("Topic root", self._topic_root)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _browse_ca_cert(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "CA certificate",
            self._ca_cert.text() or "",
            "PEM (*.pem *.crt);;All files (*)",
        )
        if path:
            self._ca_cert.setText(path)

    def load(self, settings: MQTTSettings) -> None:
        self._host.setText(settings.host or "")
        self._port.setValue(settings.port or 1883)
        self._username.setText(settings.username or "")
        self._password.setText(settings.password or "")
        self._use_tls.setChecked(settings.use_tls)
        self._ca_cert.setText(settings.ca_certificate or "")
        self._tls_insecure.setChecked(settings.tls_insecure)
        self._topic_root.setText(settings.topic_root or "")

    def settings(self) -> MQTTSettings:
        return MQTTSettings(
            host=(self._host.text() or "localhost").strip(),
            port=self._port.value(),
            username=self._username.text().strip(),
            password=self._password.text().strip(),
            use_tls=self._use_tls.isChecked(),
            ca_certificate=self._ca_cert.text().strip(),
            tls_insecure=self._tls_insecure.isChecked(),
            topic_root=self._topic_root.text().strip(),
        )
