from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from brokers.base.interface import BrokerInterface, Timeframe
from core.market.selection import AssetClass
from core.market.snapshot import MarketSnapshot
from core.pipeline import ATIPPipeline, PipelineResult
from core.signal.lifecycle import SignalLifecycle, SignalLifecycleState


class ContinuousMonitorError(Exception):
    """Erreur liée au monitoring continu."""


@dataclass(frozen=True)
class MonitoringResult:
    """
    Résultat d'une analyse effectuée sur une nouvelle barre clôturée.

    Le monitor observe et analyse uniquement.
    Aucune exécution d'ordre n'est effectuée ici.
    """

    symbol: str
    asset_class: AssetClass
    timeframe: Timeframe
    bar_timestamp: object
    pipeline_result: PipelineResult
    lifecycle: SignalLifecycle


class ContinuousMonitor:
    """
    Orchestrateur du monitoring analytique continu.

    Responsabilités :
    - récupérer les données clôturées ;
    - détecter les nouvelles barres ;
    - construire un MarketSnapshot ;
    - déléguer l'analyse au pipeline canonique ;
    - gérer le cycle de vie du signal.

    Responsabilités explicitement exclues :
    - exécution d'ordres ;
    - gestion de positions MT5 ;
    - modification de compte ;
    - décision automatique de trading.
    """

    def __init__(
        self,
        broker: BrokerInterface,
        pipeline: ATIPPipeline,
        lookback: int = 500,
    ) -> None:
        if lookback <= 0:
            raise ValueError("lookback doit être supérieur à 0.")

        self._broker = broker
        self._pipeline = pipeline
        self._lookback = lookback

        self._last_processed_timestamp: Optional[object] = None
        self._active_lifecycle: Optional[SignalLifecycle] = None

    @property
    def last_processed_timestamp(self) -> Optional[object]:
        return self._last_processed_timestamp

    @property
    def active_lifecycle(self) -> Optional[SignalLifecycle]:
        return self._active_lifecycle

    def has_new_closed_bar(
        self,
        symbol: str,
        timeframe: Timeframe,
    ) -> bool:
        """
        Vérifie si une nouvelle barre clôturée est disponible.

        Cette méthode ne lance aucune analyse.
        """

        if not self._broker.is_connected():
            raise ContinuousMonitorError(
                "Broker non connecté — impossible de surveiller le marché."
            )

        bars = self._broker.get_closed_ohlcv(
            symbol,
            timeframe,
            count=1,
        )

        if not bars:
            return False

        latest_timestamp = max(
            bar.timestamp
            for bar in bars
        )

        return (
            self._last_processed_timestamp is None
            or latest_timestamp > self._last_processed_timestamp
        )

    def analyze_latest_closed_bar(
        self,
        symbol: str,
        asset_class: AssetClass,
        timeframe: Timeframe,
    ) -> Optional[MonitoringResult]:
       

        if not self._broker.is_connected():
            raise ContinuousMonitorError(
                "Broker non connecté — impossible de surveiller le marché."
            )

        bars = self._broker.get_closed_ohlcv(
            symbol,
            timeframe,
            count=self._lookback,
        )

        if not bars:
            return None

        ordered_bars = tuple(
            sorted(
                bars,
                key=lambda bar: bar.timestamp,
            )
        )

        latest_timestamp = ordered_bars[-1].timestamp

        if (
            self._last_processed_timestamp is not None
            and latest_timestamp <= self._last_processed_timestamp
        ):
            return None


        snapshot = MarketSnapshot(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            timestamp=latest_timestamp,
            bars=ordered_bars,
        )

        pipeline_result = self._pipeline.process(snapshot)

        lifecycle = SignalLifecycle.from_signal(
            pipeline_result.signal
        )

        self._last_processed_timestamp = latest_timestamp
        self._active_lifecycle = lifecycle

        return MonitoringResult(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            bar_timestamp=latest_timestamp,
            pipeline_result=pipeline_result,
            lifecycle=lifecycle,
        )