"""
MomentumFeatures — RSI, Rate of Change, momentum brut (section 7).
Historique insuffisant → None explicite, jamais 0 (section 7 et 16).
"""
from core.features.calculators.base import FeatureCalculator
from core.features.domain.ohlcv_series import OHLCVSeries


def rsi(closes: list[float], period: int) -> float | None:
    if len(closes) < period + 1:
        return None

    window = closes[-(period + 1) :]
    gains = []
    losses = []
    for prev, curr in zip(window, window[1:]):
        change = curr - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0  # série plate : ni surachat ni survente
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def rate_of_change(closes: list[float], period: int) -> float | None:
    if len(closes) < period + 1:
        return None
    reference = closes[-(period + 1)]
    if reference == 0:
        return None
    return (closes[-1] - reference) / reference * 100


class MomentumFeatures(FeatureCalculator):
    def __init__(self, rsi_period: int = 14, roc_period: int = 10, momentum_period: int = 10):
        self._rsi_period = rsi_period
        self._roc_period = roc_period
        self._momentum_period = momentum_period

    @property
    def name(self) -> str:
        return "momentum"

    def compute(self, series: OHLCVSeries) -> dict[str, float | None]:
        if series.last() is None:
            return {}

        closes = series.closes()

        momentum = None
        if len(closes) >= self._momentum_period + 1:
            momentum = closes[-1] - closes[-(self._momentum_period + 1)]

        return {
            f"rsi_{self._rsi_period}": rsi(closes, self._rsi_period),
            f"roc_{self._roc_period}": rate_of_change(closes, self._roc_period),
            f"momentum_{self._momentum_period}": momentum,
        }
