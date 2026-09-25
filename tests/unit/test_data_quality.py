from datetime import datetime, timedelta, timezone

from brokers.base.interface import OHLCVBar, Timeframe
from core.data.quality_engine import DataQualityStatus


def _bar(ts, o=1.0, h=1.1, l=0.9, c=1.05, v=100.0):
    return OHLCVBar(timestamp=ts, open=o, high=h, low=l, close=c, volume=v, spread=1.0)


def test_valid_series_returns_valid_status(quality_engine):
    now = datetime.now(timezone.utc)
    bars = [_bar(now - timedelta(minutes=15 * i)) for i in range(20, 0, -1)]
    report = quality_engine.evaluate(bars, Timeframe.M15)
    assert report.status == DataQualityStatus.VALID
    assert report.score == 1.0
    assert report.issues == []


def test_empty_series_is_invalid(quality_engine):
    report = quality_engine.evaluate([], Timeframe.M15)
    assert report.status == DataQualityStatus.INVALID
    assert report.score == 0.0


def test_invalid_ohlc_high_less_than_low_is_detected(quality_engine):
    now = datetime.now(timezone.utc)
    bad_bar = _bar(now, o=1.0, h=0.5, l=0.9, c=0.7)  # high < low
    report = quality_engine.evaluate([bad_bar], Timeframe.M15)
    assert report.status == DataQualityStatus.INVALID
    assert any("high < low" in issue for issue in report.issues)


def test_gap_in_series_is_detected(quality_engine):
    now = datetime.now(timezone.utc)
    bars = [
        _bar(now - timedelta(minutes=15)),
        _bar(now - timedelta(hours=5)),  # trou important avant la bougie précédente
    ]
    report = quality_engine.evaluate(bars, Timeframe.M15)
    assert any("Trou de données" in issue for issue in report.issues)


def test_duplicate_timestamps_are_detected(quality_engine):
    now = datetime.now(timezone.utc)
    bars = [_bar(now), _bar(now)]
    report = quality_engine.evaluate(bars, Timeframe.M15)
    assert any("dupliquée" in issue for issue in report.issues)


def test_stale_data_is_flagged(quality_engine):
    old_ts = datetime.now(timezone.utc) - timedelta(days=2)
    bars = [_bar(old_ts)]
    report = quality_engine.evaluate(bars, Timeframe.M15)
    assert any("trop ancienne" in issue for issue in report.issues)
