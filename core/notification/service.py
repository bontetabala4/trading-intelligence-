"""
Notification Service & Deduplication (Step 8).
"""
from abc import ABC, abstractmethod
from email.message import EmailMessage
import logging
import smtplib
from typing import Dict, Set
from datetime import datetime, timezone
import uuid

from core.signal.domain import FinalSignal, FinalSignalDirection, NotificationRecord, NotificationStatus

logger = logging.getLogger("atip.notification")


class BaseNotificationAdapter(ABC):
    @abstractmethod
    def send(self, recipient: str, message: str) -> bool:
        pass


class MockNotificationAdapter(BaseNotificationAdapter):
    def __init__(self, should_fail: bool = False):
        self.sent_messages = []
        self.should_fail = should_fail

    def send(self, recipient: str, message: str) -> bool:
        if self.should_fail:
            return False
        self.sent_messages.append({"recipient": recipient, "message": message})
        return True


class DisabledNotificationAdapter(BaseNotificationAdapter):
    """Explicit no-op when no notification provider is configured."""

    def send(self, recipient: str, message: str) -> bool:
        logger.warning(
            "Notification delivery skipped: no provider is configured for recipient %s.",
            recipient,
        )
        return False


class SMTPNotificationAdapter(BaseNotificationAdapter):
    """Small SMTP adapter, activated only by explicit environment configuration."""

    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        starttls: bool = True,
        smtp_factory=smtplib.SMTP,
    ) -> None:
        if not host or not sender or port <= 0:
            raise ValueError("SMTP host, port, and sender are required.")
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._starttls = starttls
        self._smtp_factory = smtp_factory

    def send(self, recipient: str, message: str) -> bool:
        email = EmailMessage()
        email["Subject"] = "ATIP — notification analytique"
        email["From"] = self._sender
        email["To"] = recipient
        email.set_content(message)

        try:
            with self._smtp_factory(self._host, self._port, timeout=10) as client:
                if self._starttls:
                    client.starttls()
                if self._username and self._password:
                    client.login(self._username, self._password)
                client.send_message(email)
            return True
        except (OSError, smtplib.SMTPException) as exc:
            logger.warning("SMTP notification delivery failed: %s", exc)
            return False


def build_notification_adapter(settings=None) -> BaseNotificationAdapter:
    """Build the configured adapter; no configuration means explicitly disabled."""
    if settings is None:
        from configs.settings import get_settings

        settings = get_settings()

    if not settings.notification_email_enabled:
        return DisabledNotificationAdapter()

    required = (
        settings.notification_smtp_host,
        settings.notification_smtp_port,
        settings.notification_smtp_from,
    )
    if any(value is None for value in required):
        logger.warning("SMTP notifications are enabled but configuration is incomplete.")
        return DisabledNotificationAdapter()

    return SMTPNotificationAdapter(
        host=settings.notification_smtp_host,
        port=settings.notification_smtp_port,
        sender=settings.notification_smtp_from,
        username=settings.notification_smtp_username,
        password=settings.notification_smtp_password,
        starttls=settings.notification_smtp_starttls,
    )


class NotificationService:
    def __init__(self, adapter: BaseNotificationAdapter):
        self.adapter = adapter
        self._processed_keys: Set[str] = set()
        self.records: Dict[str, NotificationRecord] = {}

    def format_notification(self, signal: FinalSignal) -> str:
        if signal.direction in (FinalSignalDirection.BUY, FinalSignalDirection.SELL):
            reasons_fmt = "\n".join([f"- {r}" for r in signal.reasons])
            return (
                f"ATIP — SIGNAL ANALYTIQUE\n\n"
                f"Signal: {signal.direction.value}\n"
                f"Symbol: {signal.symbol}\n"
                f"Timeframe: {signal.timeframe}\n\n"
                f"Regime: {signal.market_regime}\n"
                f"Strategy: {signal.strategy}\n\n"
                f"Opportunity: {signal.opportunity_status}\n"
                f"Score: {signal.opportunity_score:.2f}\n\n"
                f"Risk: {signal.risk_status}\n"
                f"Data Quality: {signal.data_quality_status}\n\n"
                f"Reasons:\n{reasons_fmt}\n\n"
                f"Decision:\nHuman confirmation required before manual action in MT5."
            )
        else:
            return (
                f"ATIP — NO TRADE\n\n"
                f"Symbol: {signal.symbol}\n"
                f"Timeframe: {signal.timeframe}\n\n"
                f"Reason: {signal.no_trade_reason.value}\n"
                f"Details: {', '.join(signal.reasons)}\n\n"
                f"No action recommended."
            )

    def notify(self, signal: FinalSignal, recipient: str = "trader_default") -> NotificationRecord:
        key = signal.deduplication_key
        record_id = str(uuid.uuid4())

        if key in self._processed_keys:
            logger.info(f"Duplicate notification suppressed for key: {key}")
            record = NotificationRecord(
                notification_id=record_id,
                signal_id=signal.signal_id,
                deduplication_key=key,
                recipient=recipient,
                channel=self.adapter.__class__.__name__,
                content="",
                status=NotificationStatus.SKIPPED_DUPLICATE,
                timestamp=datetime.now(timezone.utc),
            )
            self.records[record_id] = record
            return record

        message = self.format_notification(signal)
        success = self.adapter.send(recipient, message)

        if success:
            self._processed_keys.add(key)
            status = NotificationStatus.SENT
            error_msg = None
        else:
            status = NotificationStatus.FAILED
            error_msg = "Adapter delivery failed"

        record = NotificationRecord(
            notification_id=record_id,
            signal_id=signal.signal_id,
            deduplication_key=key,
            recipient=recipient,
            channel=self.adapter.__class__.__name__,
            content=message,
            status=status,
            timestamp=datetime.now(timezone.utc),
            error_message=error_msg,
        )
        self.records[record_id] = record
        return record
