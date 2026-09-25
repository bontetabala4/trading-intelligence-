"""
FeatureSet — ensemble des features calculées pour (symbol, timeframe, timestamp).
MarketContext — regroupe FeatureSet + prix + qualité des données ; conçu
pour être étendu plus tard (regime, structure, liquidity, session, macro —
section 11) SANS que cette étape n'implémente ces champs futurs.
"""
from dataclasses import dataclass, field
from datetime import datetime

from brokers.base.interface import Timeframe
from core.data.quality_engine import DataQualityReport
from core.market.selection import AssetClass


@dataclass(frozen=True)
class FeatureSet:
    symbol: str
    timeframe: Timeframe
    timestamp: datetime
    values: dict[str, float | None]
    # Traçabilité (section 22/20) : quel calculateur a produit quelles clés,
    # utile pour déboguer une feature manquante sans deviner sa source.
    metadata: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> float | None:
        return self.values.get(key)

    def is_available(self, key: str) -> bool:
        return self.values.get(key) is not None


@dataclass(frozen=True)
class MarketContext:
    symbol: str
    asset_class: AssetClass
    timeframe: Timeframe
    timestamp: datetime
    price: float
    features: FeatureSet
    data_quality: DataQualityReport
    # Champs volontairement absents à l'Étape 3 (préparés pour plus tard,
    # section 11) : market_regime, market_structure, liquidity, session,
    # macro_context, strategy_context. Ne pas les ajouter en dur ici tant
    # que les moteurs correspondants n'existent pas (YAGNI, section 23).
