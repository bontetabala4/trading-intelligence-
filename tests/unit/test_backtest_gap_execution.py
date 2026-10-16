from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.backtest.domain import BacktestCostModel, ExitReason
from core.backtest.virtual_outcome import VirtualOutcomeEngine
from core.signal.domain import FinalSignal, FinalSignalDirection, NoTradeReason


def _signal(direction: FinalSignalDirection, stop: float, target: float) -> FinalSignal:
    return FinalSignal(
        signal_id="gap-test",
        symbol="EURUSD",
        asset_class="forex",
        timeframe="M15",
        timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        direction=direction,
        no_trade_reason=NoTradeReason.NONE,
        strategy="TREND_FOLLOWING",
        market_regime="TRENDING_BULL",
        opportunity_status="VALID",
        opportunity_score=1.0,
        risk_status="APPROVED",
        risk_score=1.0,
        data_quality_status="VALID",
        reasons=[],
        evidence={},
        entry_reference=100.0,
        stop_reference=stop,
        target_reference=target,
        risk_reward=2.0,
    )


def _bar(open_price: float, high: float, low: float) -> SimpleNamespace:
    return SimpleNamespace(
        open=open_price,
        high=high,
        low=low,
        timestamp=datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc),
    )


def test_long_stop_gap_fills_at_bid_open_not_stop_level():
    model = BacktestCostModel(price_basis="BID", slippage_points=0.0)
    trade = VirtualOutcomeEngine.create_trade_from_signal(
        _signal(FinalSignalDirection.BUY, stop=99.0, target=103.0),
        entry_price=100.0,
        cost_model=model,
    )
    assert trade is not None

    result = VirtualOutcomeEngine.evaluate_trade(
        trade, _bar(open_price=98.5, high=100.0, low=98.2), model
    )

    assert result.exit_reason == ExitReason.GAP_STOP_HIT
    assert result.exit_price == pytest.approx(98.5)
    assert result.gross_result_r == pytest.approx(-1.5)


def test_short_stop_gap_fills_at_ask_open_not_stop_level():
    model = BacktestCostModel(price_basis="ASK", slippage_points=0.0)
    trade = VirtualOutcomeEngine.create_trade_from_signal(
        _signal(FinalSignalDirection.SELL, stop=101.0, target=97.0),
        entry_price=100.0,
        cost_model=model,
    )
    assert trade is not None

    result = VirtualOutcomeEngine.evaluate_trade(
        trade, _bar(open_price=101.2, high=101.5, low=100.8), model
    )

    assert result.exit_reason == ExitReason.GAP_STOP_HIT
    assert result.exit_price == pytest.approx(101.2)
    assert result.gross_result_r == pytest.approx(-1.2)


def test_gap_through_stop_takes_precedence_over_ambiguous_intrabar_range():
    model = BacktestCostModel(price_basis="BID", slippage_points=0.0)
    trade = VirtualOutcomeEngine.create_trade_from_signal(
        _signal(FinalSignalDirection.BUY, stop=99.0, target=103.0),
        entry_price=100.0,
        cost_model=model,
    )
    assert trade is not None

    # The bar opens below the stop, then spans both stop and target levels.
    # The opening gap establishes that the stop was already breached first.
    result = VirtualOutcomeEngine.evaluate_trade(
        trade, _bar(open_price=98.5, high=103.5, low=98.0), model
    )

    assert result.exit_reason == ExitReason.GAP_STOP_HIT
    assert result.exit_price == pytest.approx(98.5)


def test_missing_open_is_rejected_instead_of_silently_ignoring_gaps():
    model = BacktestCostModel(price_basis="BID")
    trade = VirtualOutcomeEngine.create_trade_from_signal(
        _signal(FinalSignalDirection.BUY, stop=99.0, target=103.0),
        entry_price=100.0,
        cost_model=model,
    )
    assert trade is not None
    bar_without_open = SimpleNamespace(
        high=100.5,
        low=98.5,
        timestamp=datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="prix open.*requis"):
        VirtualOutcomeEngine.evaluate_trade(trade, bar_without_open, model)
