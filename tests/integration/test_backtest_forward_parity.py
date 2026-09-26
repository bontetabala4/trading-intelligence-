from datetime import datetime, timedelta, timezone

from brokers.base.interface import OHLCVBar, Timeframe

from core.pipeline import ATIPPipeline, MarketSnapshot
from core.signal.domain import FinalSignalDirection


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


def test_backtest_forward_same_snapshot_same_signal():
    """
    Vérifie la parité déterministe :

        même snapshot
              ↓
        même ATIPPipeline
              ↓
        même FinalSignal

    Le test vérifie les éléments importants du signal final.
    """

    bars = build_bars()

    pipeline = ATIPPipeline()

    snapshot = MarketSnapshot(
    symbol="EURUSD",
    asset_class="forex",
    timeframe=Timeframe.M15,
    timestamp=bars[-1].timestamp,
    bars=bars,
    )
    result_a = pipeline.process(snapshot)
    result_b = pipeline.process(snapshot)

    signal_a = result_a.signal
    signal_b = result_b.signal

    assert signal_a.direction == signal_b.direction
    assert signal_a.no_trade_reason == signal_b.no_trade_reason

    assert signal_a.market_regime == signal_b.market_regime
    assert signal_a.strategy == signal_b.strategy

    assert signal_a.opportunity_status == signal_b.opportunity_status
    assert signal_a.opportunity_score == signal_b.opportunity_score

    assert signal_a.risk_status == signal_b.risk_status

    assert signal_a.entry_reference == signal_b.entry_reference
    assert signal_a.stop_reference == signal_b.stop_reference
    assert signal_a.target_reference == signal_b.target_reference
    assert isinstance(signal_a.signal_id, str) and signal_a.signal_id
    assert isinstance(signal_b.signal_id, str) and signal_b.signal_id