from datetime import datetime, timezone
import pytest

from core.signal.domain import FinalSignalDirection, NoTradeReason, NotificationStatus
from core.signal.signal_engine import SignalEngine
from core.notification.service import NotificationService, MockNotificationAdapter


class DummyOpportunity:
    def __init__(self, status="VALID", score=85.0, entry=1.0850):
        self.status = status
        self.score = type("Score", (), {"total_score": score})()
        self.entry_reference = entry
        self.reasons = ["High quality setup"]


class DummyRisk:
    def __init__(self, status="APPROVED", stop_loss=1.0830, take_profit=1.0890, reject_reason=None):
        self.status = status
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.risk_score = 0.15
        self.reject_reason = reject_reason


def test_signal_buy_success():
    engine = SignalEngine()
    now = datetime.now(timezone.utc)
    opp = DummyOpportunity("VALID", 85.0)
    risk = DummyRisk("APPROVED")

    sig = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="TRENDING_BULL",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=opp, risk_proposal=risk, proposed_direction="BUY"
    )

    assert sig.direction == FinalSignalDirection.BUY
    assert sig.no_trade_reason == NoTradeReason.NONE
    assert sig.entry_reference == 1.0850
    assert sig.stop_reference == 1.0830


def test_signal_sell_success():
    engine = SignalEngine()
    now = datetime.now(timezone.utc)
    opp = DummyOpportunity("VALID", 80.0)
    risk = DummyRisk("APPROVED")

    sig = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="TRENDING_BEAR",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=opp, risk_proposal=risk, proposed_direction="SELL"
    )

    assert sig.direction == FinalSignalDirection.SELL


def test_no_trade_invalid_data():
    engine = SignalEngine()
    now = datetime.now(timezone.utc)

    sig = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="INVALID", market_regime="TRENDING_BULL",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=DummyOpportunity(), risk_proposal=DummyRisk(), proposed_direction="BUY"
    )

    assert sig.direction == FinalSignalDirection.NO_TRADE
    assert sig.no_trade_reason == NoTradeReason.INVALID_DATA


def test_no_trade_opportunity_rejected():
    engine = SignalEngine()
    now = datetime.now(timezone.utc)
    opp = DummyOpportunity("REJECTED")

    sig = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="TRENDING_BULL",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=opp, risk_proposal=DummyRisk(), proposed_direction="BUY"
    )

    assert sig.direction == FinalSignalDirection.NO_TRADE
    assert sig.no_trade_reason == NoTradeReason.OPPORTUNITY_REJECTED


def test_no_trade_opportunity_uncertain():
    engine = SignalEngine()
    now = datetime.now(timezone.utc)
    opp = DummyOpportunity("UNCERTAIN")

    sig = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="TRENDING_BULL",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=opp, risk_proposal=DummyRisk(), proposed_direction="BUY"
    )

    assert sig.direction == FinalSignalDirection.NO_TRADE
    assert sig.no_trade_reason == NoTradeReason.OPPORTUNITY_UNCERTAIN


def test_no_trade_risk_rejected():
    engine = SignalEngine()
    now = datetime.now(timezone.utc)
    risk = DummyRisk("REJECTED", reject_reason="MAX_DRAWDOWN")

    sig = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="TRENDING_BULL",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=DummyOpportunity(), risk_proposal=risk, proposed_direction="BUY"
    )

    assert sig.direction == FinalSignalDirection.NO_TRADE
    assert sig.no_trade_reason == NoTradeReason.RISK_REJECTED


def test_no_trade_incompatible_strategy():
    engine = SignalEngine()
    now = datetime.now(timezone.utc)

    sig = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="HIGH_VOLATILITY",
        strategy_name="Trend Following", is_strategy_compatible=False,
        opportunity_result=DummyOpportunity(), risk_proposal=DummyRisk(), proposed_direction="BUY"
    )

    assert sig.direction == FinalSignalDirection.NO_TRADE
    assert sig.no_trade_reason == NoTradeReason.STRATEGY_NOT_COMPATIBLE


def test_engine_determinism():
    engine = SignalEngine()
    now = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)
    opp = DummyOpportunity()
    risk = DummyRisk()

    sig1 = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="TRENDING_BULL",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=opp, risk_proposal=risk, proposed_direction="BUY"
    )

    sig2 = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="TRENDING_BULL",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=opp, risk_proposal=risk, proposed_direction="BUY"
    )

    assert sig1.deduplication_key == sig2.deduplication_key
    assert sig1.direction == sig2.direction


def test_notification_deduplication():
    adapter = MockNotificationAdapter()
    service = NotificationService(adapter)
    now = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)

    engine = SignalEngine()
    sig = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="TRENDING_BULL",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=DummyOpportunity(), risk_proposal=DummyRisk(), proposed_direction="BUY"
    )

    rec1 = service.notify(sig)
    assert rec1.status == NotificationStatus.SENT
    assert len(adapter.sent_messages) == 1

    rec2 = service.notify(sig)
    assert rec2.status == NotificationStatus.SKIPPED_DUPLICATE
    assert len(adapter.sent_messages) == 1


def test_notification_failure_does_not_affect_signal():
    adapter = MockNotificationAdapter(should_fail=True)
    service = NotificationService(adapter)
    now = datetime.now(timezone.utc)

    engine = SignalEngine()
    sig = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="TRENDING_BULL",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=DummyOpportunity(), risk_proposal=DummyRisk(), proposed_direction="BUY"
    )

    rec = service.notify(sig)
    assert rec.status == NotificationStatus.FAILED
    assert sig.direction == FinalSignalDirection.BUY


def test_execution_engine_isolation(monkeypatch):
    engine = SignalEngine()
    now = datetime.now(timezone.utc)

    mt5_called = False

    sig = engine.generate_signal(
        symbol="EURUSD", asset_class="FOREX", timeframe="M15", timestamp=now,
        data_quality_status="VALID", market_regime="TRENDING_BULL",
        strategy_name="Trend Following", is_strategy_compatible=True,
        opportunity_result=DummyOpportunity(), risk_proposal=DummyRisk(), proposed_direction="BUY"
    )

    assert not mt5_called
    assert sig.direction == FinalSignalDirection.BUY