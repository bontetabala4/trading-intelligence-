from datetime import datetime, timezone

import pytest

from core.signal.domain import (
    FinalSignal,
    FinalSignalDirection,
    NoTradeReason,
)
from core.signal.lifecycle import (
    SignalLifecycle,
    SignalLifecycleState,
)


def make_signal(
    direction: FinalSignalDirection = FinalSignalDirection.BUY,
) -> FinalSignal:
    return FinalSignal(
        signal_id="test-signal-001",
        symbol="EURUSD",
        asset_class="forex",
        timeframe="M15",
        timestamp=datetime(2026, 9, 30, 4, 30, tzinfo=timezone.utc),
        direction=direction,
        no_trade_reason=(
            NoTradeReason.NONE
            if direction != FinalSignalDirection.NO_TRADE
            else NoTradeReason.OPPORTUNITY_REJECTED
        ),
        strategy="TREND_FOLLOWING",
        market_regime="TRENDING_BEAR",
        opportunity_status="VALID",
        opportunity_score=100.0,
        risk_status="APPROVED",
        risk_score=0.0,
        data_quality_status="VALID",
        reasons=["test"],
        evidence={},
    )


def test_new_signal_from_buy_signal():
    lifecycle = SignalLifecycle.from_signal(make_signal())

    assert lifecycle.signal_id == "test-signal-001"
    assert lifecycle.state == SignalLifecycleState.NEW_SIGNAL
    assert lifecycle.reason is None


def test_new_signal_can_become_active():
    lifecycle = SignalLifecycle.from_signal(make_signal())

    active = lifecycle.activate()

    assert active.state == SignalLifecycleState.ACTIVE
    assert active.signal_id == lifecycle.signal_id


def test_active_signal_can_be_invalidated():
    lifecycle = SignalLifecycle.from_signal(make_signal()).activate()

    invalidated = lifecycle.invalidate("Régime de marché changé.")

    assert invalidated.state == SignalLifecycleState.INVALIDATED
    assert invalidated.reason == "Régime de marché changé."


def test_active_signal_can_expire():
    lifecycle = SignalLifecycle.from_signal(make_signal()).activate()

    expired = lifecycle.expire()

    assert expired.state == SignalLifecycleState.EXPIRED
    assert expired.reason == "Signal expiré."


def test_no_trade_signal_has_no_trade_lifecycle():
    lifecycle = SignalLifecycle.from_signal(
        make_signal(FinalSignalDirection.NO_TRADE)
    )

    assert lifecycle.state == SignalLifecycleState.NO_TRADE
    assert lifecycle.reason == NoTradeReason.OPPORTUNITY_REJECTED.value


def test_invalid_transition_from_invalidated():
    lifecycle = SignalLifecycle.from_signal(make_signal()).invalidate(
        "Signal invalidé."
    )

    with pytest.raises(ValueError, match="Transition invalide"):
        lifecycle.activate()


def test_invalid_transition_from_expired():
    lifecycle = SignalLifecycle.from_signal(make_signal()).expire()

    with pytest.raises(ValueError, match="Transition invalide"):
        lifecycle.invalidate("Nouvelle raison")


def test_empty_invalidation_reason_is_rejected():
    lifecycle = SignalLifecycle.from_signal(make_signal())

    with pytest.raises(
        ValueError,
        match="raison d'invalidation",
    ):
        lifecycle.invalidate("   ")