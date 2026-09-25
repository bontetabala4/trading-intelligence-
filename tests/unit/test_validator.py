from datetime import datetime, timedelta, timezone

from brokers.base.interface import OHLCVBar, Timeframe
from core.data.validator import MarketDataValidator
from core.market.selection import AssetClass


def _bar(ts, o=1.0, h=1.1, l=0.9, c=1.05, v=100.0):
    return OHLCVBar(timestamp=ts, open=o, high=h, low=l, close=c, volume=v, spread=1.0)


def test_weekend_gap_is_classified_as_expected():
    validator = MarketDataValidator()
    # Vendredi 20:00 UTC -> Lundi 00:00 UTC : trou classique de week-end Forex.
    friday = datetime(2026, 9, 18, 20, 0, tzinfo=timezone.utc)  # vendredi
    monday = datetime(2026, 9, 21, 0, 0, tzinfo=timezone.utc)   # lundi
    bars = [_bar(friday), _bar(monday)]

    result = validator.validate(bars, Timeframe.H1, AssetClass.FOREX)

    assert len(result.expected_gaps) == 1
    assert len(result.unexpected_gaps) == 0


def test_weekday_gap_is_classified_as_unexpected():
    validator = MarketDataValidator()
    monday_10 = datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc)
    monday_14 = datetime(2026, 9, 21, 14, 0, tzinfo=timezone.utc)  # trou en pleine semaine
    bars = [_bar(monday_10), _bar(monday_14)]

    result = validator.validate(bars, Timeframe.H1, AssetClass.FOREX)

    assert len(result.unexpected_gaps) == 1
    assert len(result.expected_gaps) == 0


def test_crypto_weekend_gap_is_never_expected():
    """Le crypto trade 24/7 — un trou le week-end reste un trou inattendu."""
    validator = MarketDataValidator()
    saturday_10 = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
    saturday_16 = datetime(2026, 9, 19, 16, 0, tzinfo=timezone.utc)
    bars = [_bar(saturday_10), _bar(saturday_16)]

    result = validator.validate(bars, Timeframe.H1, AssetClass.CRYPTO)

    assert len(result.unexpected_gaps) == 1
    assert len(result.expected_gaps) == 0


def test_quality_report_exposes_coverage_stats():
    validator = MarketDataValidator()
    now = datetime.now(timezone.utc)
    bars = [_bar(now - timedelta(minutes=15 * i)) for i in range(10, 0, -1)]

    result = validator.validate(bars, Timeframe.M15, AssetClass.METALS)

    assert result.quality.first_timestamp == min(b.timestamp for b in bars)
    assert result.quality.last_timestamp == max(b.timestamp for b in bars)
    assert result.quality.duplicate_count == 0
    assert result.quality.invalid_count == 0
