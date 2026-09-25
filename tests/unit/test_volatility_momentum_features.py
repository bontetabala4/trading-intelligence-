from datetime import datetime, timedelta, timezone

from brokers.base.interface import OHLCVBar
from core.features.calculators.momentum import MomentumFeatures, rate_of_change, rsi
from core.features.calculators.volatility import VolatilityFeatures, true_range
from core.features.domain.ohlcv_series import OHLCVSeries


def _bars_hlc(triples: list[tuple[float, float, float]]) -> list[OHLCVBar]:
    now = datetime.now(timezone.utc)
    return [
        OHLCVBar(timestamp=now + timedelta(minutes=i), open=c, high=h, low=l, close=c, volume=100)
        for i, (h, l, c) in enumerate(triples)
    ]


def test_true_range_without_previous_close():
    assert true_range(105, 100, None) == 5


def test_true_range_with_gap_up():
    # prev_close très bas -> le vrai range doit inclure l'écart
    assert true_range(105, 100, 90) == 15  # |105-90|


def test_atr_insufficient_history_returns_none():
    calc = VolatilityFeatures(atr_period=14)
    bars = _bars_hlc([(101, 99, 100)] * 5)
    result = calc.compute(OHLCVSeries.from_bars(bars))
    assert result["atr_14"] is None


def test_atr_computed_with_enough_history():
    calc = VolatilityFeatures(atr_period=3)
    bars = _bars_hlc([(101, 99, 100), (102, 98, 100), (103, 97, 100), (104, 96, 100)])
    result = calc.compute(OHLCVSeries.from_bars(bars))
    assert result["atr_3"] is not None
    assert result["atr_3"] > 0


def test_rolling_stddev_zero_for_flat_series():
    calc = VolatilityFeatures(stddev_period=5)
    bars = _bars_hlc([(101, 99, 100)] * 5)
    result = calc.compute(OHLCVSeries.from_bars(bars))
    assert result["rolling_stddev_5"] == 0.0


def test_rsi_insufficient_data_returns_none():
    assert rsi([100, 101, 102], period=14) is None


def test_rsi_all_gains_is_100():
    closes = [100 + i for i in range(15)]  # strictement croissant
    assert rsi(closes, period=14) == 100.0


def test_rsi_all_losses_is_0():
    closes = [100 - i for i in range(15)]  # strictement décroissant
    assert rsi(closes, period=14) == 0.0


def test_roc_insufficient_data_returns_none():
    assert rate_of_change([100, 101], period=10) is None


def test_roc_computed_correctly():
    closes = [100] * 10 + [110]
    result = rate_of_change(closes, period=10)
    assert result == 10.0  # (110-100)/100 * 100


def test_momentum_features_never_defaults_to_zero_when_unavailable():
    calc = MomentumFeatures(rsi_period=14, roc_period=10, momentum_period=10)
    bars = _bars_hlc([(101, 99, 100)] * 3)  # historique très insuffisant
    result = calc.compute(OHLCVSeries.from_bars(bars))

    assert result["rsi_14"] is None
    assert result["roc_10"] is None
    assert result["momentum_10"] is None
    # Vérifie explicitement qu'aucune valeur n'a été silencieusement mise à 0.
    assert all(v is None for v in result.values())
