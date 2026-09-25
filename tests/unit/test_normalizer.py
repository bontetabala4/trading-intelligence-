from datetime import datetime, timezone

from brokers.base.interface import OHLCVBar
from core.data.normalizer import TimestampNormalizer


def test_already_utc_timestamp_is_unchanged():
    normalizer = TimestampNormalizer()
    ts = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)
    bar = OHLCVBar(timestamp=ts, open=1, high=1.1, low=0.9, close=1.0, volume=100)

    normalized = normalizer.normalize_bar(bar)

    assert normalized.timestamp == ts
    assert normalized.timestamp.tzinfo is not None


def test_naive_timestamp_is_localized_to_source_timezone_then_converted_to_utc():
    normalizer = TimestampNormalizer(source_timezone="Africa/Kinshasa")  # UTC+1, pas de DST
    naive_ts = datetime(2026, 9, 22, 10, 0)  # sans tzinfo
    bar = OHLCVBar(timestamp=naive_ts, open=1, high=1.1, low=0.9, close=1.0, volume=100)

    normalized = normalizer.normalize_bar(bar)

    assert normalized.timestamp.tzinfo == timezone.utc
    assert normalized.timestamp.hour == 9  # 10h Kinshasa (UTC+1) -> 9h UTC


def test_normalize_batch_preserves_order_and_count():
    normalizer = TimestampNormalizer()
    bars = [
        OHLCVBar(
            timestamp=datetime(2026, 9, 22, h, 0, tzinfo=timezone.utc),
            open=1, high=1.1, low=0.9, close=1.0, volume=100,
        )
        for h in range(5)
    ]

    result = normalizer.normalize_batch(bars)

    assert len(result) == 5
    assert [b.timestamp.hour for b in result] == [0, 1, 2, 3, 4]
