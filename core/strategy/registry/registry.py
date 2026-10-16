"""
StrategyRegistry — Registre centralisé des stratégies quantitatives de l'ATIP.
Gère les métadonnées, statuts (ENABLED, DISABLED, EXPERIMENTAL, UNSUPPORTED_DATA),
les filtres de compatibilité et l'instanciation des stratégies.
"""
from typing import Dict, List, Optional

from core.strategy.strategies.base import BaseStrategy
from core.strategy.strategies.trend_following import TrendFollowingStrategy
from core.strategy.strategies.mean_reversion import MeanReversionStrategy
from core.strategy.strategies.macro_trend import MacroTrendStrategy
from core.strategy.strategies.breakout import BreakoutPriceActionStrategy
from core.strategy.strategies.fibonacci_pullback import FibonacciPullbackStrategy
from core.strategy.strategies.multi_timeframe import MultiTimeframeStrategy
from core.strategy.domain.enums import StrategyID, StrategyStatus
from core.strategy.domain.models import StrategyMetadata


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: Dict[str, BaseStrategy] = {}
        self._metadata: Dict[str, StrategyMetadata] = {}

    def register(
        self,
        strategy: BaseStrategy,
        metadata: StrategyMetadata,
    ) -> None:
        key = (
            metadata.strategy_id.value
            if hasattr(metadata.strategy_id, "value")
            else str(metadata.strategy_id)
        )
        self._strategies[key] = strategy
        self._metadata[key] = metadata

    def register_catalog_entry(self, metadata: StrategyMetadata) -> None:
        """Adds a visible strategy catalog entry without making it executable.

        This is used for strategies whose required data or simulation capabilities
        are not implemented yet.  A catalog entry can never be returned by
        ``get_active_strategies`` and therefore cannot emit a signal.
        """
        key = metadata.strategy_id.value
        self._metadata[key] = metadata

    def unregister(self, strategy_id: str) -> None:
        self._strategies.pop(strategy_id, None)
        self._metadata.pop(strategy_id, None)

    def get_strategy(self, strategy_id: str) -> Optional[BaseStrategy]:
        return self._strategies.get(strategy_id)

    def get_metadata(self, strategy_id: str) -> Optional[StrategyMetadata]:
        return self._metadata.get(strategy_id)

    def list_all_metadata(self) -> List[StrategyMetadata]:
        return list(self._metadata.values())

    def get_active_strategies(
        self,
        asset_class: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> List[BaseStrategy]:
        """Retourne uniquement les stratégies activées compatibles."""
        active: List[BaseStrategy] = []
        for key, strategy in self._strategies.items():
            meta = self._metadata.get(key)
            if not meta or meta.status != StrategyStatus.ENABLED:
                continue
            if asset_class and asset_class.upper() not in [
                ac.upper() for ac in meta.supported_asset_classes
            ]:
                continue
            if timeframe and timeframe.upper() not in [
                tf.upper() for tf in meta.supported_timeframes
            ]:
                continue
            active.append(strategy)
        return active


def default_strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()

    # 1. Trend Following
    trend_strat = TrendFollowingStrategy()
    registry.register(
        trend_strat,
        StrategyMetadata(
            strategy_id=StrategyID.TREND_FOLLOWING,
            name="Trend Following",
            version="1.0.0",
            description=(
                "Stratégie de suivi de tendance basée sur les alignements "
                "EMA et RSI"
            ),
            status=StrategyStatus.ENABLED,
            compatible_regimes=trend_strat.compatible_regimes,
            supported_asset_classes=["FOREX", "CRYPTO", "EQUITY"],
            supported_timeframes=["M15", "H1", "H4", "D1"],
            parameters={"ema_fast": 20, "ema_slow": 50, "rsi_period": 14},
        ),
    )

    # 2. Mean Reversion
    mr_strat = MeanReversionStrategy()
    registry.register(
        mr_strat,
        StrategyMetadata(
            strategy_id=StrategyID.MEAN_REVERSION,
            name="Mean Reversion",
            version="1.0.0",
            description=(
                "Stratégie de retour à la moyenne active uniquement en "
                "régime de range"
            ),
            status=StrategyStatus.ENABLED,
            compatible_regimes=mr_strat.compatible_regimes,
            supported_asset_classes=["FOREX"],
            supported_timeframes=["M15", "H1"],
            parameters={
                "rsi_oversold": 30.0,
                "rsi_overbought": 70.0,
                "risk_reward": 2.0,
            },
        ),
    )

    # 3. Macro Trend (Paul Tudor Jones inspiration — EMA 200)
    macro_strat = MacroTrendStrategy()
    registry.register(
        macro_strat,
        StrategyMetadata(
            strategy_id=StrategyID.EMA200_MACRO_TREND,
            name="Macro Trend EMA 200",
            version="1.0.0",
            description=(
                "Biais directionnel macroéconomique strict dicté par l'EMA 200 "
                "avec confirmation RSI/momentum."
            ),
            status=StrategyStatus.EXPERIMENTAL,
            compatible_regimes=macro_strat.compatible_regimes,
            supported_asset_classes=["FOREX", "CRYPTO", "EQUITY", "COMMODITIES"],
            supported_timeframes=["H1", "H4", "D1"],
            inspiration="Paul Tudor Jones (High-level bias concept)",
            parameters={"ema_period": 200, "risk_reward": 2.0},
        ),
    )

    # 4. Breakout / Price Action (Jesse Livermore inspiration)
    breakout_strat = BreakoutPriceActionStrategy()
    registry.register(
        breakout_strat,
        StrategyMetadata(
            strategy_id=StrategyID.BREAKOUT_PRICE_ACTION,
            name="Breakout Price Action",
            version="1.0.0",
            description=(
                "Cassure de range ou niveau clé avec confirmation "
                "de volume et expansion de volatilité."
            ),
            status=StrategyStatus.EXPERIMENTAL,
            compatible_regimes=breakout_strat.compatible_regimes,
            supported_asset_classes=["FOREX", "CRYPTO", "EQUITY", "COMMODITIES"],
            supported_timeframes=["M15", "H1", "H4"],
            inspiration="Jesse Livermore (Pivotal points & ranges)",
            parameters={"lookback_period": 20, "risk_reward": 2.0},
        ),
    )

    # 5. Fibonacci Pullback
    fib_strat = FibonacciPullbackStrategy()
    registry.register(
        fib_strat,
        StrategyMetadata(
            strategy_id=StrategyID.FIBONACCI_PULLBACK,
            name="Fibonacci Pullback",
            version="1.0.0",
            description=(
                "Retracement causal dans la Golden Zone (38.2% - 61.8%) "
                "avec confirmation de reprise."
            ),
            status=StrategyStatus.EXPERIMENTAL,
            compatible_regimes=fib_strat.compatible_regimes,
            supported_asset_classes=["FOREX", "CRYPTO", "COMMODITIES"],
            supported_timeframes=["M15", "H1", "H4"],
            parameters={"fib_entry_min": 0.382, "fib_entry_max": 0.618, "risk_reward": 2.0},
        ),
    )

    # 6. Multi-Timeframe (MTF)
    mtf_strat = MultiTimeframeStrategy()
    registry.register(
        mtf_strat,
        StrategyMetadata(
            strategy_id=StrategyID.MULTI_TIMEFRAME,
            name="Multi-Timeframe Alignment",
            version="1.0.0",
            description=(
                "Alignement strict entre biais directionnel HTF (H4/D1) "
                "et confirmation d'entrée LTF (M15)."
            ),
            status=StrategyStatus.EXPERIMENTAL,
            compatible_regimes=mtf_strat.compatible_regimes,
            supported_asset_classes=["FOREX", "CRYPTO", "EQUITY"],
            supported_timeframes=["M15", "H1"],
            parameters={"htf_lookback": "H4", "ltf_entry": "M15"},
        ),
    )

    # These entries intentionally have no strategy implementation.  OHLCV-only
    # data and the single-leg simulator cannot validate their required mechanics.
    registry.register_catalog_entry(
        StrategyMetadata(
            strategy_id=StrategyID.PAIRS_TRADING,
            name="Pairs Trading / Statistical Arbitrage",
            version="0.1.0",
            description=(
                "Deux jambes synchronisées, relation statistique stable et coûts "
                "des deux instruments sont requis avant toute expérimentation."
            ),
            status=StrategyStatus.UNSUPPORTED_DATA,
            supported_asset_classes=["EQUITY", "FOREX", "CRYPTO"],
            supported_timeframes=["M15", "H1", "H4", "D1"],
            parameters={"requirements": ["synchronised_pairs", "two_leg_ledger", "cointegration_validation"]},
        )
    )
    registry.register_catalog_entry(
        StrategyMetadata(
            strategy_id=StrategyID.MARKET_MAKING,
            name="Market Making",
            version="0.1.0",
            description=(
                "Nécessite un flux bid/ask, idéalement la profondeur de carnet, "
                "un modèle de latence et une gestion d'inventaire."
            ),
            status=StrategyStatus.UNSUPPORTED_DATA,
            supported_asset_classes=["CRYPTO", "EQUITY", "FOREX"],
            supported_timeframes=[],
            parameters={"requirements": ["bid_ask_feed", "order_book", "inventory_risk_model"]},
        )
    )

    return registry

