"""
Configuration déclarative des marchés à collecter (section 21 Étape 2).

Choix : Python/Pydantic plutôt que YAML — cohérent avec le reste du projet
(Settings via pydantic-settings), validé au chargement, et permet de
réutiliser directement les enums existants (AssetClass, Timeframe) sans
couche de parsing supplémentaire.
"""
from pydantic import BaseModel

from brokers.base.interface import Timeframe
from core.market.selection import AssetClass


class MarketConfigEntry(BaseModel):
    symbol: str
    asset_class: AssetClass
    timeframes: list[Timeframe]


# Liste par défaut, volontairement restreinte aux symboles connus du
# MockMT5Adapter (voir brokers/mt5/mock_adapter.py) pour que la config par
# défaut fonctionne immédiatement en dev/CI sans terminal MT5 réel.
DEFAULT_MARKETS: list[MarketConfigEntry] = [
    MarketConfigEntry(
        symbol="XAUUSD",
        asset_class=AssetClass.METALS,
        timeframes=[Timeframe.M15, Timeframe.H1],
    ),
    MarketConfigEntry(
        symbol="EURUSD",
        asset_class=AssetClass.FOREX,
        timeframes=[Timeframe.M15, Timeframe.H1],
    ),
]


def get_markets_config() -> list[MarketConfigEntry]:
    """
    Point d'extension unique : à terme, remplaçable par un chargement depuis
    fichier/DB sans changer les appelants. Retourne la config par défaut
    pour l'Étape 2.
    """
    return DEFAULT_MARKETS
