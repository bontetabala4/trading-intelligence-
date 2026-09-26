from datetime import datetime, timedelta, timezone

import pytest

from brokers.base.interface import (
    OHLCVBar,
    Timeframe,
)

from core.pipeline import MarketSnapshot


def test_snapshot_rejects_future_bar():

    timestamp_t = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=timezone.utc,
    )

    future_timestamp = (
        timestamp_t
        + timedelta(minutes=15)
    )

    bars = (
        OHLCVBar(
            timestamp=timestamp_t,
            open=1.1,
            high=1.11,
            low=1.09,
            close=1.105,
            volume=1000,
        ),
        OHLCVBar(
            timestamp=future_timestamp,
            open=1.105,
            high=1.12,
            low=1.10,
            close=1.115,
            volume=1000,
        ),
    )

    with pytest.raises(ValueError):

        MarketSnapshot(
            symbol="EURUSD",
            asset_class="FX",
            timeframe=Timeframe.M15,
            timestamp=timestamp_t,
            bars=bars,
        )