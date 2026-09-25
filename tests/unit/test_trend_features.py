from datetime import datetime, timedelta, timezone

from brokers.base.interface import OHLCVBar
from core.features.calculators.trend import TrendFeatures, ema_series, sma
from core.features.domain.ohlcv_series import OHLCVSeries


def _bars_with_closes(closes: list[float]) -> list[OHLCVBar]:
    now = datetime.now(timezone.utc)
    return [
        OHLCVBar(
            timestamp=now + timedelta(minutes=i), open=c, high=c + 1, low=c - 1, close=c, volume=100,
        )
        for i, c in enumerate(closes)
    ]


def test_sma_insufficient_data_returns_none():
    assert sma([1, 2, 3], period=5) is None


def test_sma_exact_period():
    assert sma([1, 2, 3, 4, 5], period=5) == 3.0


def test_sma_uses_only_last_n_values():
    assert sma([100, 100, 1, 2, 3, 4, 5], period=5) == 3.0


def test_ema_insufficient_data_returns_all_none():
    result = ema_series([1, 2, 3], period=5)
    assert result == [None, None, None]


def test_ema_seeded_with_sma_then_recursive():
    values = [1, 2, 3, 4, 5, 6, 7]
    result = ema_series(values, period=5)
    assert result[:4] == [None, None, None, None]
    assert result[4] == sum(values[:5]) / 5  # seed = SMA des 5 premiers


def test_trend_features_configurable_periods():
    calc = TrendFeatures(sma_periods=[3], ema_periods=[3])
    bars = _bars_with_closes([10, 11, 12, 13, 14])
    series = OHLCVSeries.from_bars(bars)

    result = calc.compute(series)

    assert result["sma_3"] == (12 + 13 + 14) / 3
    assert result["distance_to_sma_3"] == 14 - result["sma_3"]
    assert result["ema_3"] is not None
    assert result["distance_to_ema_3"] == 14 - result["ema_3"]


def test_trend_features_insufficient_history_returns_none():
    calc = TrendFeatures(sma_periods=[20], ema_periods=[20])
    bars = _bars_with_closes([10, 11, 12])
    series = OHLCVSeries.from_bars(bars)

    result = calc.compute(series)

    assert result["sma_20"] is None
    assert result["distance_to_sma_20"] is None
    assert result["ema_20"] is None
