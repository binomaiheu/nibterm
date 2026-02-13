from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings


@dataclass
class MQTTSettings:
    host: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""
    use_tls: bool = False
    ca_certificate: str = ""
    tls_insecure: bool = False
    topic_root: str = ""

    def to_qsettings(self, settings: QSettings) -> None:
        settings.setValue("mqtt/host", self.host)
        settings.setValue("mqtt/port", self.port)
        settings.setValue("mqtt/username", self.username)
        settings.setValue("mqtt/password", self.password)
        settings.setValue("mqtt/use_tls", self.use_tls)
        settings.setValue("mqtt/ca_certificate", self.ca_certificate)
        settings.setValue("mqtt/tls_insecure", self.tls_insecure)
        settings.setValue("mqtt/topic_root", self.topic_root)

    @staticmethod
    def from_qsettings(settings: QSettings) -> "MQTTSettings":
        return MQTTSettings(
            host=settings.value("mqtt/host", "localhost", str),
            port=settings.value("mqtt/port", 1883, int),
            username=settings.value("mqtt/username", "", str),
            password=settings.value("mqtt/password", "", str),
            use_tls=settings.value("mqtt/use_tls", False, bool),
            ca_certificate=settings.value("mqtt/ca_certificate", "", str),
            tls_insecure=settings.value("mqtt/tls_insecure", False, bool),
            topic_root=settings.value("mqtt/topic_root", "", str),
        )
