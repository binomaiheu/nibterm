from __future__ import annotations

import logging
import ssl
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

import paho.mqtt.client as mqtt
from PySide6.QtCore import QObject, Signal

from .settings import MQTTSettings

if TYPE_CHECKING:
    pass

# MQTT v3.1.1 (0-5) and common MQTT v5 CONNACK reason codes
_CONNACK_REASONS = {
    0: "Accepted",
    1: "Unsupported protocol version",
    2: "Identifier rejected",
    3: "Server unavailable",
    4: "Bad username or password",
    5: "Not authorized",
    # MQTT v5 (e.g. 135 = 0x87)
    135: "Not authorized (broker rejected credentials or ACL)",
}


def _connack_message(rc: int) -> str:
    msg = _CONNACK_REASONS.get(rc)
    return f"{msg} ({rc})" if msg else str(rc)


class MQTTManager(QObject):
    message_received = Signal(str, bytes)
    connection_changed = Signal(bool)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._client: mqtt.Client | None = None
        self._settings: MQTTSettings | None = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def set_settings(self, settings: MQTTSettings) -> None:
        self._settings = settings

    def connect_(self, settings: MQTTSettings | None = None) -> bool:
        if settings is not None:
            self._settings = settings
        if self._settings is None:
            self.error.emit("No MQTT settings")
            return False
        if self._client is not None:
            self.disconnect_()
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="",
            protocol=mqtt.MQTTv311,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        host = self._settings.host or "localhost"
        port = self._settings.port or 1883
        if self._settings.use_tls:
            ctx = ssl.create_default_context()
            if self._settings.ca_certificate:
                ctx.load_verify_locations(self._settings.ca_certificate)
            if self._settings.tls_insecure:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            self._client.tls_set_context(ctx)

        try:
            if self._settings.username:
                self._client.username_pw_set(
                    self._settings.username,
                    self._settings.password or None,
                )
            self._client.connect(host, port=port, keepalive=60)
        except Exception as e:
            logger.exception("MQTT connect failed")
            self.error.emit(str(e))
            self._client = None
            return False

        self._client.loop_start()
        return True

    def disconnect_(self) -> None:
        if self._client is None:
            return
        self._client.loop_stop()
        self._client.disconnect()
        self._client = None
        self._connected = False
        self.connection_changed.emit(False)

    def subscribe(self, topic: str) -> None:
        if self._client is None or not self._connected:
            return
        self._client.subscribe(topic, qos=0)

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: None,
        flags: dict,
        reason_code: int,
        properties: mqtt.Properties | None,
    ) -> None:
        rc = getattr(reason_code, "value", reason_code)
        if rc != 0:
            self.error.emit(f"Connect failed: {_connack_message(rc)}")
            self.connection_changed.emit(False)
            # Stop the client so it doesn't keep auto-reconnecting and spamming the error
            if self._client is not None:
                try:
                    self._client.loop_stop()
                    self._client.disconnect()
                except Exception:
                    logger.debug("Error during MQTT cleanup after failed connect", exc_info=True)
                self._client = None
            return
        self._connected = True
        self.connection_changed.emit(True)
        root = (self._settings and self._settings.topic_root) or ""
        subscribe_topic = f"{root}/#" if root else "#"
        client.subscribe(subscribe_topic, qos=0)

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: None,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: int,
        properties: mqtt.Properties | None,
    ) -> None:
        self._connected = False
        self.connection_changed.emit(False)

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: None,
        message: mqtt.MQTTMessage,
    ) -> None:
        self.message_received.emit(message.topic, message.payload)
