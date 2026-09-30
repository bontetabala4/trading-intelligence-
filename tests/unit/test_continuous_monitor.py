from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from brokers.base.interface import OHLCVBar, Timeframe
from core.market.selection import AssetClass
from core.monitor.continuous_monitor import (
    ContinuousMonitor,
    ContinuousMonitorError,
)
from core.pipeline import PipelineResult
from core.signal.domain import (
    FinalSignal,
    FinalSignalDirection,
    NoTradeReason,
)
from core.signal.lifecycle import SignalLifecycleState


def make_bar(timestamp: datetime, close: float = 1.1000) -> OHLCVBar:
    return OHLCVBar(
        timestamp=timestamp,
        open=close,
        high=close + 0.0010,
        low=close - 0.0010,
        close=close,
        volume=1000.0,
    )


def make_signal(
    timestamp: datetime,
    direction: FinalSignalDirection = FinalSignalDirection.BUY,
) -> FinalSignal:
    return FinalSignal(
        signal_id=f"signal-{timestamp.isoformat()}",
        symbol="EURUSD",
        asset_class=AssetClass.FOREX,
        timeframe="M15",
        timestamp=timestamp,
        direction=direction,
        no_trade_reason=(
            NoTradeReason.NONE
            if direction != FinalSignalDirection.NO_TRADE
            else NoTradeReason.OPPORTUNITY_REJECTED
        ),
        strategy="TREND_FOLLOWING",
        market_regime="TRENDING_BULL",
        opportunity_status="VALID",
        opportunity_score=100.0,
        risk_status="APPROVED",
        risk_score=0.0,
        data_quality_status="VALID",
        reasons=["test"],
        evidence={},
    )


def make_pipeline_result(timestamp: datetime) -> PipelineResult:
    return PipelineResult(
        signal=make_signal(timestamp),
        data_quality_status="VALID",
        data_quality_score=1.0,
        features={},
        regime=Mock(),
        strategy_signal=None,
        opportunity_result=None,
    )


def make_monitor(
    bars: list[OHLCVBar],
):
    broker = Mock()
    broker.is_connected.return_value = True
    broker.get_closed_ohlcv.return_value = bars

    pipeline = Mock()

    if bars:
        pipeline.process.return_value = make_pipeline_result(
            bars[-1].timestamp
        )

    monitor = ContinuousMonitor(
        broker=broker,
        pipeline=pipeline,
        lookback=500,
    )

    return monitor, broker, pipeline


def test_first_closed_bar_is_analyzed():
    timestamp = datetime(
        2026,
        9,
        30,
        4,
        30,
        tzinfo=timezone.utc,
    )

    bars = [
        make_bar(timestamp),
    ]

    monitor, broker, pipeline = make_monitor(bars)

    result = monitor.analyze_latest_closed_bar(
        symbol="EURUSD",
        asset_class=AssetClass.FOREX,
        timeframe=Timeframe.M15,
    )

    assert result is not None
    assert result.bar_timestamp == timestamp
    assert result.lifecycle.state == SignalLifecycleState.NEW_SIGNAL

    pipeline.process.assert_called_once()


def test_same_closed_bar_is_not_analyzed_twice():
    timestamp = datetime(
        2026,
        9,
        30,
        4,
        30,
        tzinfo=timezone.utc,
    )

    bars = [
        make_bar(timestamp),
    ]

    monitor, broker, pipeline = make_monitor(bars)

    first = monitor.analyze_latest_closed_bar(
        "EURUSD",
        AssetClass.FOREX,
        Timeframe.M15,
    )

    second = monitor.analyze_latest_closed_bar(
        "EURUSD",
        AssetClass.FOREX,
        Timeframe.M15,
    )

    assert first is not None
    assert second is None
    pipeline.process.assert_called_once()


def test_new_closed_bar_is_analyzed():
    first_timestamp = datetime(
        2026,
        9,
        30,
        4,
        30,
        tzinfo=timezone.utc,
    )

    second_timestamp = datetime(
        2026,
        9,
        30,
        4,
        45,
        tzinfo=timezone.utc,
    )

    first_bars = [
        make_bar(first_timestamp),
    ]

    monitor, broker, pipeline = make_monitor(first_bars)

    first_result = monitor.analyze_latest_closed_bar(
        "EURUSD",
        AssetClass.FOREX,
        Timeframe.M15,
    )

    assert first_result is not None

    second_bars = [
        make_bar(first_timestamp),
        make_bar(second_timestamp),
    ]

    broker.get_closed_ohlcv.return_value = second_bars
    pipeline.process.return_value = make_pipeline_result(
        second_timestamp
    )

    second_result = monitor.analyze_latest_closed_bar(
        "EURUSD",
        AssetClass.FOREX,
        Timeframe.M15,
    )

    assert second_result is not None
    assert second_result.bar_timestamp == second_timestamp
    assert pipeline.process.call_count == 2


def test_has_new_closed_bar_returns_true_for_new_bar():
    timestamp = datetime(
        2026,
        9,
        30,
        4,
        30,
        tzinfo=timezone.utc,
    )

    monitor, broker, pipeline = make_monitor(
        [make_bar(timestamp)]
    )

    assert monitor.has_new_closed_bar(
        "EURUSD",
        Timeframe.M15,
    ) is True


def test_has_new_closed_bar_returns_false_after_processing():
    timestamp = datetime(
        2026,
        9,
        30,
        4,
        30,
        tzinfo=timezone.utc,
    )

    monitor, broker, pipeline = make_monitor(
        [make_bar(timestamp)]
    )

    monitor.analyze_latest_closed_bar(
        "EURUSD",
        AssetClass.FOREX,
        Timeframe.M15,
    )

    assert monitor.has_new_closed_bar(
        "EURUSD",
        Timeframe.M15,
    ) is False


def test_no_data_returns_none():
    monitor, broker, pipeline = make_monitor([])

    result = monitor.analyze_latest_closed_bar(
        "EURUSD",
        AssetClass.FOREX,
        Timeframe.M15,
    )

    assert result is None
    pipeline.process.assert_not_called()


def test_disconnected_broker_is_rejected():
    broker = Mock()
    broker.is_connected.return_value = False

    pipeline = Mock()

    monitor = ContinuousMonitor(
        broker=broker,
        pipeline=pipeline,
    )

    with pytest.raises(
        ContinuousMonitorError,
        match="Broker non connecté",
    ):
        monitor.analyze_latest_closed_bar(
            "EURUSD",
            AssetClass.FOREX,
            Timeframe.M15,
        )


def test_monitor_never_executes_orders():
    timestamp = datetime(
        2026,
        9,
        30,
        4,
        30,
        tzinfo=timezone.utc,
    )

    bars = [make_bar(timestamp)]

    monitor, broker, pipeline = make_monitor(bars)

    monitor.analyze_latest_closed_bar(
        "EURUSD",
        AssetClass.FOREX,
        Timeframe.M15,
    )

    assert not hasattr(monitor, "execute_order")
    broker.execute_order.assert_not_called()