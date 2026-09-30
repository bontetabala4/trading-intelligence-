"""
MarketObserver — premier composant "intelligent" de la plateforme.

Orchestration READ-ONLY : récupère les données via BrokerInterface,
les fait évaluer par DataQualityEngine, et produit un MarketSnapshot.
Ne prend aucune décision de trading.
"""
import logging

from brokers.base.interface import BrokerInterface, Timeframe
from core.data.quality_engine import DataQualityEngine
from core.market.selection import AssetClass
from core.market.snapshot import MarketSnapshot

logger = logging.getLogger("atip.market.observer")


class MarketObserverError(RuntimeError):
    """Levée quand un snapshot ne peut pas être construit (pas de données, etc.)."""


class MarketObserver:
    def __init__(self, broker: BrokerInterface, quality_engine: DataQualityEngine) -> None:
        self._broker = broker
        self._quality_engine = quality_engine

    def build_snapshot(
        self,
        symbol: str,
        asset_class: AssetClass,
        timeframe: Timeframe,
        lookback: int = 500,
    ) -> MarketSnapshot:
        if not self._broker.is_connected():
            raise MarketObserverError("Broker non connecté — impossible d'observer le marché.")

        symbol_info = self._broker.get_symbol_info(symbol)
        if not symbol_info.exists:
            raise MarketObserverError(f"Le symbole '{symbol}' n'existe pas chez ce broker.")

        bars = self._broker.get_closed_ohlcv(
            symbol,
            timeframe,
            count=lookback,
        )
        if not bars:
            raise MarketObserverError(f"Aucune donnée disponible pour {symbol}/{timeframe.value}.")

        quality_report = self._quality_engine.evaluate(
            bars,
            timeframe,
            asset_class,
        )

        latest = max(bars, key=lambda b: b.timestamp)

        snapshot = MarketSnapshot(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            timestamp=latest.timestamp,
            bars=tuple(
                sorted(
                    bars,
                    key=lambda bar: bar.timestamp,
                )
            ),
        )

        logger.info(
            "Snapshot construit: %s/%s status=%s score=%.3f",
            symbol,
            timeframe.value,
            quality_report.status,
            quality_report.score,
        )
        return snapshot
