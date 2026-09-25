"""
PriceFeatures — features fondamentales calculées à partir d'une seule
bougie + la précédente pour le retour close-to-close (section 4).
"""
from core.features.calculators.base import FeatureCalculator
from core.features.domain.ohlcv_series import OHLCVSeries


class PriceFeatures(FeatureCalculator):
    @property
    def name(self) -> str:
        return "price"

    def compute(self, series: OHLCVSeries) -> dict[str, float | None]:
        bar = series.last()
        if bar is None:
            return self._empty()

        candle_range = bar.high - bar.low
        body = bar.close - bar.open
        abs_body = abs(body)

        # Cas High == Low (section 4) : aucune division, tout ratio dépendant
        # du range reste explicitement None plutôt qu'une division par zéro.
        if candle_range == 0:
            body_ratio = None
            upper_wick = None
            lower_wick = None
        else:
            upper_wick = bar.high - max(bar.open, bar.close)
            lower_wick = min(bar.open, bar.close) - bar.low
            body_ratio = abs_body / candle_range

        direction = 1.0 if body > 0 else (-1.0 if body < 0 else 0.0)

        pct_change = (body / bar.open) if bar.open != 0 else None

        close_to_close_return = None
        if len(series) >= 2:
            prev = series.bars[-2]
            if prev.close != 0:
                close_to_close_return = (bar.close - prev.close) / prev.close

        return {
            "open_to_close_return": pct_change,
            "close_to_close_return": close_to_close_return,
            "high_low_range": candle_range,
            "body": body,
            "abs_body": abs_body,
            "upper_wick": upper_wick,
            "lower_wick": lower_wick,
            "body_ratio": body_ratio,
            "direction": direction,
            "close_to_open_distance": bar.close - bar.open,
            "close_to_high_distance": bar.high - bar.close,
            "close_to_low_distance": bar.close - bar.low,
        }

    @staticmethod
    def _empty() -> dict[str, float | None]:
        keys = [
            "open_to_close_return", "close_to_close_return", "high_low_range",
            "body", "abs_body", "upper_wick", "lower_wick", "body_ratio",
            "direction", "close_to_open_distance", "close_to_high_distance",
            "close_to_low_distance",
        ]
        return dict.fromkeys(keys, None)
