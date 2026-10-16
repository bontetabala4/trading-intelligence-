from dataclasses import dataclass

from configs.settings import Settings
from core.notification.service import (
    DisabledNotificationAdapter,
    SMTPNotificationAdapter,
    build_notification_adapter,
)


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_args = None
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, message):
        self.messages.append(message)


def test_smtp_adapter_delivers_only_through_its_explicit_configuration():
    adapter = SMTPNotificationAdapter(
        host="smtp.example.test",
        port=587,
        sender="atip@example.test",
        username="user",
        password="secret",
        smtp_factory=FakeSMTP,
    )

    assert adapter.send("trader@example.test", "No order is executed.") is True
    client = FakeSMTP.instances[-1]
    assert client.started_tls is True
    assert client.login_args == ("user", "secret")
    assert client.messages[0]["To"] == "trader@example.test"


def test_notification_provider_is_disabled_without_explicit_configuration():
    disabled = build_notification_adapter(Settings())
    assert isinstance(disabled, DisabledNotificationAdapter)

    incomplete = build_notification_adapter(
        Settings(notification_email_enabled=True, notification_smtp_host="smtp.example.test")
    )
    assert isinstance(incomplete, DisabledNotificationAdapter)
