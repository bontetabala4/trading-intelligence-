from datetime import datetime, timedelta, timezone

from brokers.base.interface import OHLCVBar, Timeframe

from core.pipeline import ATIPPipeline, MarketSnapshot
from core.risk.domain.enums import RiskStatus


def build_bars():
    bars = []

    price = 1.1000
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    for i in range(250):
        timestamp = start + timedelta(minutes=i)

        open_price = price
        close_price = price + (0.0001 if i % 2 == 0 else -0.00005)

        high_price = max(open_price, close_price) + 0.0002
        low_price = min(open_price, close_price) - 0.0002

        bars.append(
            OHLCVBar(
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=1000 + i,
                spread=0.0001,
                tick_volume=1000 + i,
                real_volume=1000 + i,
            )
        )

        price = close_price

    return bars


def build_snapshot(bars):
    return MarketSnapshot(
        symbol="EURUSD",
        asset_class="forex",
        timeframe=Timeframe.M15,
        timestamp=bars[-1].timestamp,
        bars=bars,
    )


def assert_strategy_signal_parity(forward_result, backtest_result):
    forward = forward_result.strategy_signal
    backtest = backtest_result.strategy_signal

    assert (forward is None) == (backtest is None)

    if forward is None:
        return

    assert forward.symbol == backtest.symbol
    assert forward.timeframe == backtest.timeframe
    assert forward.timestamp == backtest.timestamp
    assert forward.strategy_id == backtest.strategy_id
    assert forward.signal == backtest.signal
    assert forward.strength == backtest.strength
    assert forward.regime_context == backtest.regime_context
    assert forward.evidence == backtest.evidence
    assert forward.suggested_sl_distance == backtest.suggested_sl_distance
    assert forward.suggested_tp_distance == backtest.suggested_tp_distance


def assert_order_proposal_parity(forward_result, backtest_result):
    forward = forward_result.risk_proposal
    backtest = backtest_result.risk_proposal

    assert (forward is None) == (backtest is None)

    if forward is None:
        return

    assert forward.symbol == backtest.symbol
    assert forward.signal_type == backtest.signal_type
    assert forward.strategy_id == backtest.strategy_id

    assert forward.volume_lots == backtest.volume_lots
    assert (
        forward.risk_amount_account_currency
        == backtest.risk_amount_account_currency
    )
    assert forward.risk_percentage == backtest.risk_percentage

    assert forward.stop_loss == backtest.stop_loss
    assert forward.take_profit == backtest.take_profit

    assert forward.timestamp == backtest.timestamp
    assert forward.status == backtest.status
    assert forward.reject_reason == backtest.reject_reason
    assert forward.engine_version == backtest.engine_version


def assert_final_signal_parity(forward_result, backtest_result):
    forward = forward_result.signal
    backtest = backtest_result.signal

    assert forward.direction == backtest.direction
    assert forward.no_trade_reason == backtest.no_trade_reason

    assert forward.market_regime == backtest.market_regime
    assert forward.strategy == backtest.strategy

    assert forward.opportunity_status == backtest.opportunity_status
    assert forward.opportunity_score == backtest.opportunity_score

    assert forward.risk_status == backtest.risk_status

    assert forward.entry_reference == backtest.entry_reference
    assert forward.stop_reference == backtest.stop_reference
    assert forward.target_reference == backtest.target_reference


def test_backtest_forward_deterministic_pipeline_parity():
    """
    Vérifie que le même MarketSnapshot, traité avec deux instances
    indépendantes du pipeline canonique ATIP, produit exactement
    les mêmes décisions analytiques et de risque.

    Chemin testé :

        MarketSnapshot
              ↓
        ATIPPipeline
              ↓
        StrategySignal
              ↓
        RiskEngine
              ↓
        OrderProposal
              ↓
        FinalSignal

    Le test ne compare pas seulement FinalSignal :
    il vérifie les contrats intermédiaires critiques.
    """

    bars = build_bars()
    snapshot = build_snapshot(bars)

    # ------------------------------------------------------------------
    # FORWARD / PAPER PATH
    # ------------------------------------------------------------------

    forward_pipeline = ATIPPipeline()

    forward_result = forward_pipeline.process(snapshot)

    # ------------------------------------------------------------------
    # BACKTEST PATH
    # ------------------------------------------------------------------
    #
    # Même snapshot, nouvelle instance indépendante du pipeline.
    # Cela évite de masquer un état mutable partagé entre les deux appels.
    #

    backtest_pipeline = ATIPPipeline()

    backtest_result = backtest_pipeline.process(snapshot)

    # ------------------------------------------------------------------
    # STRATEGY PARITY
    # ------------------------------------------------------------------

    assert_strategy_signal_parity(
        forward_result,
        backtest_result,
    )

    # ------------------------------------------------------------------
    # RISK / ORDER PROPOSAL PARITY
    # ------------------------------------------------------------------

    assert_order_proposal_parity(
        forward_result,
        backtest_result,
    )

    # ------------------------------------------------------------------
    # FINAL SIGNAL PARITY
    # ------------------------------------------------------------------

    assert_final_signal_parity(
        forward_result,
        backtest_result,
    )

    # ------------------------------------------------------------------
    # RISK STATUS CONTRACT
    # ------------------------------------------------------------------

    forward_order = forward_result.risk_proposal
    backtest_order = backtest_result.risk_proposal

    if forward_order is not None and backtest_order is not None:
        assert forward_order.status == backtest_order.status

        if forward_order.status == RiskStatus.APPROVED:
            assert forward_order.volume_lots > 0
            assert backtest_order.volume_lots > 0