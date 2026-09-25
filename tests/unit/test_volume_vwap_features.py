from datetime import datetime, timedelta, timezone

from brokers.base.interface import OHLCVBar
from core.features.calculators.volume import VolumeFeatures
from core.features.calculators.vwap import VWAPFeatures
from core.features.domain.ohlcv_series import OHLCVSeries


def _bar(tick_volume, real_volume, h=101, l=99, c=100, o=100, ts=None):
    ts = ts or datetime.now(timezone.utc)
    return OHLCVBar(
        timestamp=ts, open=o, high=h, low=l, close=c, volume=tick_volume or 0,
        tick_volume=tick_volume, real_volume=real_volume,
    )


def _series(bars: list[OHLCVBar]) -> OHLCVSeries:
    now = datetime.now(timezone.utc)
    timed = [
        OHLCVBar(
            timestamp=now + timedelta(minutes=i), open=b.open, high=b.high, low=b.low,
            close=b.close, volume=b.volume, tick_volume=b.tick_volume, real_volume=b.real_volume,
        )
        for i, b in enumerate(bars)
    ]
    return OHLCVSeries.from_bars(timed)


def test_volume_features_never_invents_real_volume():
    """Section 8 : real_volume absent -> reste None, jamais inventé."""
    calc = VolumeFeatures(rolling_period=3)
    bars = [_bar(tick_volume=100, real_volume=None) for _ in range(5)]

    result = calc.compute(_series(bars))

    assert result["real_volume"] is None
    assert result["real_volume_available"] is False
    assert result["rolling_avg_real_volume_3"] is None
    assert result["relative_real_volume"] is None
    # Le tick_volume, lui, est disponible et doit être calculé.
    assert result["tick_volume"] == 100
    assert result["rolling_avg_tick_volume_3"] == 100


def test_volume_features_uses_real_volume_when_available():
    calc = VolumeFeatures(rolling_period=3)
    bars = [_bar(tick_volume=100, real_volume=50) for _ in range(5)]

    result = calc.compute(_series(bars))

    assert result["real_volume_available"] is True
    assert result["rolling_avg_real_volume_3"] == 50


def test_vwap_unavailable_when_insufficient_history():
    calc = VWAPFeatures(period=20)
    bars = [_bar(tick_volume=100, real_volume=None) for _ in range(5)]

    result = calc.compute(_series(bars))

    assert result["vwap"] is None
    assert result["vwap_available"] is False


def test_vwap_unavailable_when_no_volume_at_all():
    calc = VWAPFeatures(period=3)
    bars = [_bar(tick_volume=None, real_volume=None) for _ in range(5)]

    result = calc.compute(_series(bars))

    assert result["vwap"] is None
    assert result["vwap_available"] is False
    assert result["vwap_volume_source"] is None


def test_vwap_prefers_real_volume_over_tick_volume():
    calc = VWAPFeatures(period=3)
    bars = [_bar(tick_volume=999, real_volume=10, h=101, l=99, c=100) for _ in range(5)]

    result = calc.compute(_series(bars))

    assert result["vwap_available"] is True
    assert result["vwap_volume_source"] == "real_volume"


def test_vwap_falls_back_to_tick_volume_when_real_volume_partially_missing():
    calc = VWAPFeatures(period=5)  # la fenêtre doit couvrir les 5 bougies, dont celle à real_volume=None
    bars = [
        _bar(tick_volume=100, real_volume=10),
        _bar(tick_volume=100, real_volume=None),  # casse la disponibilité real_volume sur la fenêtre
        _bar(tick_volume=100, real_volume=10),
        _bar(tick_volume=100, real_volume=10),
        _bar(tick_volume=100, real_volume=10),
    ]

    result = calc.compute(_series(bars))

    assert result["vwap_available"] is True
    assert result["vwap_volume_source"] == "tick_volume"


def test_vwap_computed_value_is_reasonable():
    calc = VWAPFeatures(period=3)
    bars = [_bar(tick_volume=100, real_volume=None, h=101, l=99, c=100) for _ in range(3)]

    result = calc.compute(_series(bars))

    typical_price = (101 + 99 + 100) / 3
    assert result["vwap"] == typical_price  # volume constant -> VWAP = prix typique constant
