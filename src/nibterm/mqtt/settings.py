from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings

from ..config import settings_keys as SK


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
        settings.setValue(SK.MQTT_HOST, self.host)
        settings.setValue(SK.MQTT_PORT, self.port)
        settings.setValue(SK.MQTT_USERNAME, self.username)
        settings.setValue(SK.MQTT_PASSWORD, self.password)
        settings.setValue(SK.MQTT_USE_TLS, self.use_tls)
        settings.setValue(SK.MQTT_CA_CERTIFICATE, self.ca_certificate)
        settings.setValue(SK.MQTT_TLS_INSECURE, self.tls_insecure)
        settings.setValue(SK.MQTT_TOPIC_ROOT, self.topic_root)

    @staticmethod
    def from_qsettings(settings: QSettings) -> "MQTTSettings":
        return MQTTSettings(
            host=settings.value(SK.MQTT_HOST, "localhost", str),
            port=settings.value(SK.MQTT_PORT, 1883, int),
            username=settings.value(SK.MQTT_USERNAME, "", str),
            password=settings.value(SK.MQTT_PASSWORD, "", str),
            use_tls=settings.value(SK.MQTT_USE_TLS, False, bool),
            ca_certificate=settings.value(SK.MQTT_CA_CERTIFICATE, "", str),
            tls_insecure=settings.value(SK.MQTT_TLS_INSECURE, False, bool),
            topic_root=settings.value(SK.MQTT_TOPIC_ROOT, "", str),
        )
