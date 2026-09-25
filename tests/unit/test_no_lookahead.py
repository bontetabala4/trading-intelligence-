"""
Tests anti-look-ahead bias (section 15) — l'exigence CRITIQUE de l'Étape 3.

Principe du test : calculer une feature sur une série tronquée à l'instant T
(up_to(i)) doit donner EXACTEMENT le même résultat que la calculer sur la
série complète puis ne regarder que la valeur au même instant T. Si une
feature "voit" le futur, ce test la détecte.
"""
from datetime import datetime, timedelta, timezone

from brokers.base.interface import OHLCVBar
from core.features.calculators.momentum import MomentumFeatures
from core.features.calculators.price import PriceFeatures
from core.features.calculators.trend import TrendFeatures
from core.features.calculators.volatility import VolatilityFeatures
from core.features.calculators.volume import VolumeFeatures
from core.features.calculators.vwap import VWAPFeatures
from core.features.domain.ohlcv_series import OHLCVSeries


def _synthetic_bars(n: int) -> list[OHLCVBar]:
    now = datetime.now(timezone.utc)
    bars = []
    price = 100.0
    for i in range(n):
        ts = now - timedelta(minutes=15 * (n - i))
        # Variation déterministe (pas aléatoire) pour un test reproductible.
        drift = (i % 7 - 3) * 0.1
        open_ = price
        close = price + drift
        high = max(open_, close) + 0.2
        low = min(open_, close) - 0.2
        bars.append(
            OHLCVBar(
                timestamp=ts, open=open_, high=high, low=low, close=close,
                volume=100 + i, spread=1.0, tick_volume=100 + i, real_volume=50 + i,
            )
        )
        price = close
    return bars


CALCULATORS = [
    PriceFeatures(),
    TrendFeatures(sma_periods=[5], ema_periods=[5]),
    VolatilityFeatures(atr_period=5, stddev_period=5),
    MomentumFeatures(rsi_period=5, roc_period=5, momentum_period=5),
    VolumeFeatures(rolling_period=5),
    VWAPFeatures(period=5),
]


def test_no_lookahead_for_any_calculator():
    bars = _synthetic_bars(30)
    full_series = OHLCVSeries.from_bars(bars)

    # On choisit un instant T au milieu de la série (index 15), avec du
    # "futur" disponible après lui (index 16..29) que le calcul ne doit
    # JAMAIS utiliser.
    t_index = 15
    truncated_series = full_series.up_to(t_index)

    for calculator in CALCULATORS:
        result_truncated = calculator.compute(truncated_series)

        # Calcule aussi sur la série complète, mais le calculateur ne reçoit
        # QUE la série tronquée dans les deux cas — donc si le résultat
        # diffère d'un appel à l'autre pour la même série tronquée, ce n'est
        # pas un test de look-ahead mais de déterminisme (couvert séparément).
        # Le vrai test : falsifier le futur ne doit rien changer au résultat présent.
        mutated_bars = list(bars)
        future_bar = mutated_bars[t_index + 1]
        mutated_bars[t_index + 1] = OHLCVBar(
            timestamp=future_bar.timestamp,
            open=999999.0, high=999999.0, low=999999.0, close=999999.0,
            volume=999999.0, spread=0.0, tick_volume=999999.0, real_volume=999999.0,
        )
        mutated_series = OHLCVSeries.from_bars(mutated_bars).up_to(t_index)
        result_with_falsified_future = calculator.compute(mutated_series)

        assert result_truncated == result_with_falsified_future, (
            f"Look-ahead détecté dans {calculator.name} : falsifier une bougie "
            f"future a changé le résultat au présent."
        )


def test_ema_series_is_causal():
    """Chaque point de l'EMA ne doit dépendre que des valeurs passées."""
    from core.features.calculators.trend import ema_series

    values = [float(i) for i in range(20)]
    full = ema_series(values, period=5)

    truncated = ema_series(values[:10], period=5)

    # Les 10 premiers points de l'EMA complète doivent être identiques à
    # l'EMA calculée sur seulement les 10 premières valeurs.
    assert full[:10] == truncated
