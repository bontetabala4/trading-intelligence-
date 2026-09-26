from datetime import datetime, timedelta, timezone

from brokers.base.interface import (
    OHLCVBar,
    Timeframe,
)

from core.pipeline import (
    ATIPPipeline,
    MarketSnapshot,
)


def build_bars(count=250):

    bars = []

    price = 1.1000

    start = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    for i in range(count):

        timestamp = (
            start
            + timedelta(minutes=15 * i)
        )

        close = (
            price
            + 0.0001 * (i % 7)
        )

        bars.append(
            OHLCVBar(
                timestamp=timestamp,
                open=price,
                high=close + 0.0005,
                low=price - 0.0005,
                close=close,
                volume=1000.0,
            )
        )

        price = close

    return bars


def test_pipeline_future_mutation_does_not_change_t():

    bars = build_bars()

    split_index = 200

    history_t = bars[:split_index + 1]

    future = bars[split_index + 1:]

    pipeline = ATIPPipeline()

    timestamp_t = history_t[-1].timestamp

    snapshot_t = MarketSnapshot(
        symbol="EURUSD",
        asset_class="FX",
        timeframe=Timeframe.M15,
        timestamp=timestamp_t,
        bars=tuple(history_t),
    )

    result_before = pipeline.process(
        snapshot_t
    )

    mutated_future = []

    for bar in future:

        mutated_future.append(
            OHLCVBar(
                timestamp=bar.timestamp,
                open=bar.open * 2,
                high=bar.high * 2,
                low=bar.low * 0.5,
                close=bar.close * 2,
                volume=bar.volume * 10,
            )
        )

    # On reconstruit volontairement le même snapshot T.
    snapshot_after = MarketSnapshot(
        symbol="EURUSD",
        asset_class="FX",
        timeframe=Timeframe.M15,
        timestamp=timestamp_t,
        bars=tuple(history_t),
    )

    result_after = pipeline.process(
        snapshot_after
    )

    assert (
        result_before.signal.direction
        == result_after.signal.direction
    )

    assert (
        result_before.signal.market_regime
        == result_after.signal.market_regime
    )

    assert (
        result_before.signal.strategy
        == result_after.signal.strategy
    )

    assert (
        result_before.signal.opportunity_score
        == result_after.signal.opportunity_score
    )

    assert (
        result_before.signal.stop_reference
        == result_after.signal.stop_reference
    )

    assert (
        result_before.signal.target_reference
        == result_after.signal.target_reference
    )