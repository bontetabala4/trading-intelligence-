"""
FeatureEngine — orchestre Feature Input → Feature Calculators → Feature Set
(section 3). Seul point du module features/ qui touche MarketDataRepository
(donc SQLAlchemy) — les calculateurs eux-mêmes restent agnostiques.
"""
import logging
from datetime import timezone

from brokers.base.interface import OHLCVBar, Timeframe
from core.features.domain.ohlcv_series import OHLCVSeries
from core.features.models import FeatureSet
from core.features.registry.registry import FeatureRegistry, default_registry
from database.models import MarketData

logger = logging.getLogger("atip.features.engine")


class InsufficientDataError(RuntimeError):
    """Levée quand il n'y a même pas une seule bougie disponible."""


class FeatureEngine:
    def __init__(self, registry: FeatureRegistry | None = None) -> None:
        self._registry = registry or default_registry()

    def compute_feature_set(
        self, symbol: str, timeframe: Timeframe, bars: list[OHLCVBar]
    ) -> FeatureSet:
        """
        Calcule le FeatureSet pour la DERNIÈRE bougie de `bars`. `bars` doit
        déjà être filtré pour ne contenir aucune donnée postérieure à
        l'instant visé — c'est la responsabilité de l'appelant (garantit
        l'absence de look-ahead, section 15).
        """
        series = OHLCVSeries.from_bars(bars)
        last = series.last()
        if last is None:
            raise InsufficientDataError(f"Aucune bougie disponible pour {symbol}/{timeframe.value}.")

        values: dict[str, float | None] = {}
        metadata: dict[str, str] = {}

        for calculator in self._registry.all():
            try:
                result = calculator.compute(series)
            except Exception as exc:  # noqa: BLE001 — un calculateur en échec ne doit pas planter tout le FeatureSet
                logger.error(
                    "Erreur de calcul pour %s/%s dans le calculateur '%s': %s",
                    symbol, timeframe.value, calculator.name, exc,
                )
                result = {}

            for key, value in result.items():
                if key in values:
                    logger.warning(
                        "Collision de clé de feature '%s' entre calculateurs (dernier gagne).", key
                    )
                values[key] = value
                metadata[key] = calculator.name

        logger.info(
            "FeatureSet calculé pour %s/%s @ %s (%d features, %d indisponibles)",
            symbol, timeframe.value, last.timestamp,
            len(values), sum(1 for v in values.values() if v is None),
        )

        return FeatureSet(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=last.timestamp,
            values=values,
            metadata=metadata,
        )

    @staticmethod
    def bars_from_market_data(rows: list[MarketData]) -> list[OHLCVBar]:
        """
        Convertit les modèles SQLAlchemy MarketData (Étape 2) en OHLCVBar
        génériques (Étape 1/2) — le seul point de couture entre la couche
        base de données et les calculateurs de features, qui restent ainsi
        totalement indépendants de SQLAlchemy.

        Par construction (Étape 2, TimestampNormalizer), tout ce qui est
        stocké en base est en UTC. Certains drivers (notamment SQLite, utile
        en dev/tests) ne préservent pas le tzinfo à la relecture et renvoient
        un timestamp naïf — on le réattache explicitement à UTC ici plutôt
        que de laisser une comparaison naïve/aware planter plus loin dans le
        pipeline (DataQualityEngine).
        """
        bars = []
        for row in rows:
            ts = row.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            bars.append(
                OHLCVBar(
                    timestamp=ts,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume,
                    spread=row.spread,
                    tick_volume=row.tick_volume,
                    real_volume=row.real_volume,
                )
            )
        return bars
