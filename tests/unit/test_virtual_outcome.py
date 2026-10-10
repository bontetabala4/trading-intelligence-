from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.backtest.domain import BacktestCostModel, ExitReason
from core.backtest.virtual_outcome import VirtualOutcomeEngine
from core.signal.domain import FinalSignal, FinalSignalDirection, NoTradeReason

from datetime import datetime, timezone

from core.risk.domain.enums import RiskStatus, RiskRejectReason
from core.risk.domain.models import OrderProposal
from core.strategy.domain.enums import SignalType, StrategyID

from core.backtest.domain import BacktestCostModel
from core.backtest.virtual_outcome import VirtualOutcomeEngine
from core.signal.domain import FinalSignal, FinalSignalDirection



def make_signal(
    direction=FinalSignalDirection.BUY,
    stop=99.0,
    target=103.0,
):
    return FinalSignal(
        signal_id="test-signal",
        symbol="EURUSD",
        asset_class="forex",
        timeframe="M15",
        timestamp=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        direction=direction,
        no_trade_reason=None,
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


def make_bar(
    high,
    low,
    timestamp=None,
):
    return SimpleNamespace(
        high=high,
        low=low,
        timestamp=timestamp
        or datetime(2025, 1, 1, 10, 15, tzinfo=timezone.utc),
    )


def test_create_buy_trade_applies_adverse_entry_costs():
    signal = make_signal()

    cost_model = BacktestCostModel(
        spread_points=1.0,
        point_value=0.01,
        slippage_points=2.0,
        commission_per_trade_r=0.0,
    )

    trade = VirtualOutcomeEngine.create_trade_from_signal(
        signal=signal,
        entry_price=100.0,
        cost_model=cost_model,
    )

    assert trade is not None

    # BUY:
    # slippage = 2 * 0.01 = 0.02
    # half spread = 1 * 0.01 / 2 = 0.005
    # adjusted entry = 100.025
    assert trade.entry_price == pytest.approx(100.025)

    # Risk = |100.025 - 99| = 1.025
    assert trade.risk_r_amount == pytest.approx(1.025)


def test_create_sell_trade_applies_adverse_entry_costs():
    signal = make_signal(
        direction=FinalSignalDirection.SELL,
        stop=101.0,
        target=97.0,
    )

    cost_model = BacktestCostModel(
        spread_points=1.0,
        point_value=0.01,
        slippage_points=2.0,
        commission_per_trade_r=0.0,
    )

    trade = VirtualOutcomeEngine.create_trade_from_signal(
        signal=signal,
        entry_price=100.0,
        cost_model=cost_model,
    )

    assert trade is not None

    # SELL:
    # adjusted entry = 100 - 0.02 - 0.005
    assert trade.entry_price == pytest.approx(99.975)

    assert trade.risk_r_amount == pytest.approx(1.025)


def test_ambiguous_bar_uses_stop_first():
    signal = make_signal()

    cost_model = BacktestCostModel(
        spread_points=0.0,
        point_value=0.0001,
        slippage_points=0.0,
        commission_per_trade_r=0.0,
    )

    trade = VirtualOutcomeEngine.create_trade_from_signal(
        signal=signal,
        entry_price=100.0,
        cost_model=cost_model,
    )

    bar = make_bar(
        high=103.5,
        low=98.5,
    )

    result = VirtualOutcomeEngine.evaluate_trade(
        trade=trade,
        current_bar=bar,
        cost_model=cost_model,
    )

    assert result.is_open is False
    assert result.exit_reason == ExitReason.AMBIGUOUS_BAR_STOP_HIT
    assert result.exit_price == pytest.approx(99.0)

    # Entry = 100
    # Stop = 99
    # Result = -1R
    assert result.gross_result_r == -1.0
    assert result.net_result_r == -1.0


def test_target_hit_produces_positive_two_r():
    signal = make_signal()

    cost_model = BacktestCostModel(
        spread_points=0.0,
        point_value=0.0001,
        slippage_points=0.0,
        commission_per_trade_r=0.0,
    )

    trade = VirtualOutcomeEngine.create_trade_from_signal(
        signal=signal,
        entry_price=100.0,
        cost_model=cost_model,
    )

    bar = make_bar(
        high=103.0,
        low=100.5,
    )

    result = VirtualOutcomeEngine.evaluate_trade(
        trade=trade,
        current_bar=bar,
        cost_model=cost_model,
    )

    assert result.is_open is False
    assert result.exit_reason == ExitReason.TARGET_HIT

    # Risk = 100 - 99 = 1
    # Target = 103 -> +3R
    assert result.gross_result_r == 3.0
    assert result.net_result_r == 3.0


def test_stop_hit_produces_negative_one_r():
    signal = make_signal()

    cost_model = BacktestCostModel(
        spread_points=0.0,
        point_value=0.0001,
        slippage_points=0.0,
        commission_per_trade_r=0.0,
    )

    trade = VirtualOutcomeEngine.create_trade_from_signal(
        signal=signal,
        entry_price=100.0,
        cost_model=cost_model,
    )

    bar = make_bar(
        high=100.5,
        low=99.0,
    )

    result = VirtualOutcomeEngine.evaluate_trade(
        trade=trade,
        current_bar=bar,
        cost_model=cost_model,
    )

    assert result.is_open is False
    assert result.exit_reason == ExitReason.STOP_HIT

    assert result.gross_result_r == -1.0
    assert result.net_result_r == -1.0


def test_open_trade_remains_open_when_no_level_is_hit():
    signal = make_signal()

    cost_model = BacktestCostModel(
        spread_points=0.0,
        point_value=0.0001,
        slippage_points=0.0,
        commission_per_trade_r=0.0,
    )

    trade = VirtualOutcomeEngine.create_trade_from_signal(
        signal=signal,
        entry_price=100.0,
        cost_model=cost_model,
    )

    bar = make_bar(
        high=102.0,
        low=100.0,
    )

    result = VirtualOutcomeEngine.evaluate_trade(
        trade=trade,
        current_bar=bar,
        cost_model=cost_model,
    )

    assert result.is_open is True
    assert result.exit_timestamp is None
    assert result.exit_price is None


def test_commission_is_subtracted_from_net_r():
    signal = make_signal()

    cost_model = BacktestCostModel(
        spread_points=0.0,
        point_value=0.0001,
        slippage_points=0.0,
        commission_per_trade_r=0.25,
    )

    trade = VirtualOutcomeEngine.create_trade_from_signal(
        signal=signal,
        entry_price=100.0,
        cost_model=cost_model,
    )

    bar = make_bar(
        high=103.0,
        low=100.5,
    )

    result = VirtualOutcomeEngine.evaluate_trade(
        trade=trade,
        current_bar=bar,
        cost_model=cost_model,
    )

    assert result.gross_result_r == 3.0
    assert result.net_result_r == 2.75

    

def test_create_trade_from_order_preserves_risk_contract():
    signal = FinalSignal(
        signal_id="SIG-ORDER-001",
        symbol="EURUSD",
        asset_class="forex",
        timeframe="M15",
        timestamp=datetime(2025, 1, 2, 12, 0, tzinfo=timezone.utc),
        direction=FinalSignalDirection.BUY,
        no_trade_reason=NoTradeReason.NONE,
        strategy="TREND_FOLLOWING",
        market_regime="TRENDING_BULL",
        opportunity_status="VALID",
        opportunity_score=0.90,
        risk_status="APPROVED",
        risk_score=1.0,
        data_quality_status="VALID",
        reasons=[],
        evidence={},
    )

    order_proposal = OrderProposal(
        symbol="EURUSD",
        signal_type=SignalType.BUY,
        strategy_id=StrategyID.TREND_FOLLOWING,
        volume_lots=0.66,
        stop_loss=1.0835,
        take_profit=1.0880,
        risk_amount_account_currency=100.0,
        risk_percentage=0.01,
        timestamp=signal.timestamp,
        status=RiskStatus.APPROVED,
        reject_reason=RiskRejectReason.NONE,
    )

    cost_model = BacktestCostModel(
        spread_points=0.0,
        point_value=0.0001,
        commission_per_trade_r=0.0,
        slippage_points=0.0,
    )

    trade = VirtualOutcomeEngine.create_trade_from_order(
        signal=signal,
        order_proposal=order_proposal,
        entry_price=1.0850,
        cost_model=cost_model,
    )

    assert trade is not None

    # Le Backtest reprend exactement le volume calculé par le RiskEngine.
    assert trade.volume_lots == order_proposal.volume_lots

    # Le montant de risque vient directement de l'OrderProposal.
    assert (
        trade.risk_amount_account_currency
        == order_proposal.risk_amount_account_currency
    )

    # SL/TP viennent également de l'OrderProposal.
    assert trade.stop_reference == order_proposal.stop_loss
    assert trade.target_reference == order_proposal.take_profit

    # Aucun recalcul indépendant du lot n'est effectué par le Backtest.
    assert trade.volume_lots == 0.66