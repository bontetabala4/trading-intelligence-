from datetime import datetime, timezone

from brokers.base.interface import OHLCVBar
from core.features.calculators.price import PriceFeatures
from core.features.domain.ohlcv_series import OHLCVSeries


def _bar(o, h, l, c, ts=None):
    ts = ts or datetime.now(timezone.utc)
    return OHLCVBar(timestamp=ts, open=o, high=h, low=l, close=c, volume=100)


def test_bullish_candle_features():
    calc = PriceFeatures()
    series = OHLCVSeries.from_bars([_bar(100, 105, 99, 104)])

    result = calc.compute(series)

    assert result["body"] == 4
    assert result["direction"] == 1.0
    assert result["high_low_range"] == 6
    assert result["upper_wick"] == 1  # 105 - 104
    assert result["lower_wick"] == 1  # 100 - 99


def test_bearish_candle_features():
    calc = PriceFeatures()
    series = OHLCVSeries.from_bars([_bar(104, 105, 99, 100)])

    result = calc.compute(series)

    assert result["body"] == -4
    assert result["direction"] == -1.0


def test_high_equals_low_never_divides_by_zero():
    """Section 4 : gérer explicitement High == Low sans NaN/Infinity."""
    calc = PriceFeatures()
    series = OHLCVSeries.from_bars([_bar(100, 100, 100, 100)])

    result = calc.compute(series)

    assert result["body_ratio"] is None
    assert result["upper_wick"] is None
    assert result["lower_wick"] is None
    assert result["high_low_range"] == 0


def test_close_to_close_return_requires_previous_bar():
    calc = PriceFeatures()
    single_bar_series = OHLCVSeries.from_bars([_bar(100, 105, 99, 104)])

    result = calc.compute(single_bar_series)

    assert result["close_to_close_return"] is None  # pas de bougie précédente


def test_close_to_close_return_computed_with_previous_bar():
    calc = PriceFeatures()
    bars = [_bar(100, 105, 99, 100), _bar(100, 106, 99, 105)]
    series = OHLCVSeries.from_bars(bars)

    result = calc.compute(series)

    assert result["close_to_close_return"] == 0.05  # (105-100)/100


def test_empty_series_returns_all_none():
    calc = PriceFeatures()
    result = calc.compute(OHLCVSeries.from_bars([]))
    assert all(v is None for v in result.values())
