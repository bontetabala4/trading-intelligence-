from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from brokers.base.interface import OHLCVBar, Timeframe

from core.data.quality_engine import (
    DataQualityEngine,
    DataQualityStatus,
)

from core.features.services.feature_engine import (
    FeatureEngine,
)

from core.regime.services.engine import (
    MarketRegimeEngine,
)

from core.strategy.services.StrategyEngine import (
    StrategyEngine,
)

from core.strategy.domain.models import StrategySignal
from core.strategy.domain.enums import SignalType

from core.opportunity.detector import (
    OpportunityDetector,
)

from core.opportunity.quantifier import (
    OpportunityQuantifier,
)

from core.opportunity.validator import (
    OpportunityValidator,
)

from core.opportunity.models import (
    OpportunityResult,
    ValidationStatus,
)

from core.signal.signal_engine import (
    SignalEngine,
)

from core.signal.domain import (
    FinalSignal,
    FinalSignalDirection,
)

from core.risk.services.engine import (
    RiskEngine,
)

from core.risk.domain.models import (
    AccountState,
)

from core.market.snapshot import MarketSnapshot

@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    asset_class: str
    timeframe: Timeframe
    timestamp: datetime
    bars: tuple[OHLCVBar, ...]

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError(
                "MarketSnapshot.timestamp doit être timezone-aware."
            )

        # Normalisation : accepte une liste ou un tuple en entrée,
        # mais garantit un tuple en interne pour que les comparaisons
        # ci-dessous soient fiables quel que soit le type fourni par
        # l'appelant (dataclass frozen -> object.__setattr__ requis).
        object.__setattr__(self, "bars", tuple(self.bars))

        ordered = tuple(
            sorted(
                self.bars,
                key=lambda bar: bar.timestamp,
            )
        )

        if ordered != self.bars:
            raise ValueError(
                "Les bars du MarketSnapshot doivent être triées "
                "chronologiquement."
            )

        if not self.bars:
            raise ValueError(
                "MarketSnapshot doit contenir au moins une bougie."
            )

        future_bars = [
            bar
            for bar in self.bars
            if bar.timestamp > self.timestamp
        ]

        if future_bars:
            raise ValueError(
                "Look-ahead détecté : une ou plusieurs bougies "
                "sont postérieures au timestamp du snapshot."
            )

        if self.bars[-1].timestamp != self.timestamp:
            raise ValueError(
                "La dernière bougie doit correspondre exactement "
                "au timestamp du snapshot."
            )

@dataclass(frozen=True)
class PipelineResult:
    """
    Résultat complet du pipeline.

    Les champs intermédiaires permettent :
    - audit
    - backtest
    - forward comparison
    - observabilité
    """

    signal: FinalSignal
    data_quality_status: str
    data_quality_score: float
    features: dict
    regime: object
    strategy_signal: Optional[StrategySignal]
    opportunity_result: Optional[OpportunityResult]


class ATIPPipeline:
    """
    Pipeline analytique canonique d'ATIP.

    Aucun moteur n'est instancié dynamiquement dans process().
    Les dépendances sont injectées une seule fois au constructeur.
    """

    def __init__(
        self,
        data_quality_engine: Optional[DataQualityEngine] = None,
        feature_engine: Optional[FeatureEngine] = None,
        regime_engine: Optional[MarketRegimeEngine] = None,
        strategy_engine: Optional[StrategyEngine] = None,
        opportunity_detector: Optional[OpportunityDetector] = None,
        opportunity_quantifier: Optional[OpportunityQuantifier] = None,
        opportunity_validator: Optional[OpportunityValidator] = None,
        signal_engine: Optional[SignalEngine] = None,
        risk_engine: Optional[RiskEngine] = None,
        account: Optional[AccountState] = None,
    ) -> None:

        self.data_quality_engine = (
            data_quality_engine or DataQualityEngine()
        )

        self.feature_engine = (
            feature_engine or FeatureEngine()
        )

        self.regime_engine = (
            regime_engine or MarketRegimeEngine()
        )

        self.strategy_engine = (
            strategy_engine or StrategyEngine()
        )

        self.opportunity_detector = (
            opportunity_detector or OpportunityDetector()
        )

        self.opportunity_quantifier = (
            opportunity_quantifier or OpportunityQuantifier()
        )

        self.opportunity_validator = (
            opportunity_validator or OpportunityValidator()
        )

        self.signal_engine = (
            signal_engine or SignalEngine()
        )

        self.risk_engine = (
            risk_engine or RiskEngine()
        )

        self.account = account or AccountState(
            balance=10_000.0,
            equity=10_000.0,
            free_margin=10_000.0,
            daily_pnl=0.0,
            open_positions_count=0,
        )

    def process(
        self,
        snapshot: MarketSnapshot,
        symbol_info=None,
    ) -> PipelineResult:

        # ==============================================================
        # 1. DATA QUALITY
        # ==============================================================

        quality_report = self.data_quality_engine.evaluate(
            list(snapshot.bars),
            snapshot.timeframe,
        )

        data_quality_status = quality_report.status.value
        data_quality_score = quality_report.score

        # Une donnée invalide ne doit jamais alimenter les moteurs
        # décisionnels.
        if quality_report.status == DataQualityStatus.INVALID:

            signal = self.signal_engine.generate_signal(
                symbol=snapshot.symbol,
                asset_class=snapshot.asset_class,
                timeframe=snapshot.timeframe.value,
                timestamp=snapshot.timestamp,
                data_quality_status=data_quality_status,
                market_regime="UNCERTAIN",
                strategy_name="NONE",
                is_strategy_compatible=False,
                opportunity_result=None,
                risk_proposal=None,
                proposed_direction=None,
            )

            return PipelineResult(
                signal=signal,
                data_quality_status=data_quality_status,
                data_quality_score=data_quality_score,
                features={},
                regime=None,
                strategy_signal=None,
                opportunity_result=None,
            )

        # ==============================================================
        # 2. FEATURES
        # ==============================================================

        feature_set = self.feature_engine.compute_feature_set(
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            bars=list(snapshot.bars),
        )

        features = dict(feature_set.values)

        # Alias utilisés par OpportunityDetector.
        features["close"] = snapshot.bars[-1].close

        # ==============================================================
        # 3. REGIME
        # ==============================================================

        regime = self.regime_engine.evaluate(
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe.value,
            timestamp=snapshot.timestamp,
            features=features,
            data_quality=data_quality_status,
        )

        # ==============================================================
        # 4. STRATEGY
        # ==============================================================

        strategy_signals = self.strategy_engine.evaluate_all(
            regime=regime,
            features=features,
        )

        strategy_signal = self._select_strategy_signal(
            strategy_signals
        )

        # Aucun signal stratégique exploitable.
        if strategy_signal is None:

            signal = self.signal_engine.generate_signal(
                symbol=snapshot.symbol,
                asset_class=snapshot.asset_class,
                timeframe=snapshot.timeframe.value,
                timestamp=snapshot.timestamp,
                data_quality_status=data_quality_status,
                market_regime=regime.regime.value,
                strategy_name="NONE",
                is_strategy_compatible=False,
                opportunity_result=None,
                risk_proposal=None,
                proposed_direction=None,
            )

            return PipelineResult(
                signal=signal,
                data_quality_status=data_quality_status,
                data_quality_score=data_quality_score,
                features=features,
                regime=regime,
                strategy_signal=None,
                opportunity_result=None,
            )

        # ==============================================================
        # 5. OPPORTUNITY DETECTION
        # ==============================================================

        strategy_evaluation = {
            "signal": strategy_signal.signal.value,
            "is_compatible": True,
            "strength": strategy_signal.strength,
            "evidence": strategy_signal.evidence,
        }

        opportunity = self.opportunity_detector.detect(
            symbol=snapshot.symbol,
            asset_class=snapshot.asset_class,
            timeframe=snapshot.timeframe.value,
            timestamp=snapshot.timestamp,
            market_regime=regime.regime.value,
            strategy_name=strategy_signal.strategy_id.value,
            strategy_evaluation=strategy_evaluation,
            features=features,
            data_quality_score=data_quality_score,
        )

        if opportunity is None:

            signal = self.signal_engine.generate_signal(
                symbol=snapshot.symbol,
                asset_class=snapshot.asset_class,
                timeframe=snapshot.timeframe.value,
                timestamp=snapshot.timestamp,
                data_quality_status=data_quality_status,
                market_regime=regime.regime.value,
                strategy_name=strategy_signal.strategy_id.value,
                is_strategy_compatible=True,
                opportunity_result=None,
                risk_proposal=None,
                proposed_direction=None,
            )

            return PipelineResult(
                signal=signal,
                data_quality_status=data_quality_status,
                data_quality_score=data_quality_score,
                features=features,
                regime=regime,
                strategy_signal=strategy_signal,
                opportunity_result=None,
            )

        # ==============================================================
        # 6. OPPORTUNITY QUANTIFICATION
        # ==============================================================

        opportunity_score = (
            self.opportunity_quantifier.quantify(
                opportunity
            )
        )

        # ==============================================================
        # 7. OPPORTUNITY VALIDATION
        # ==============================================================

        opportunity_result = (
            self.opportunity_validator.validate(
                opportunity,
                opportunity_score,
            )
        )

        # ==============================================================
        # 8. RISK
        # ==============================================================

        risk_proposal = None

        if opportunity_result.status == ValidationStatus.VALID:

            current_price = snapshot.bars[-1].close

            risk_proposal = self.risk_engine.evaluate_signal(
                signal=strategy_signal,
                account=self.account,
                current_price=current_price,
                current_spread_pips=1.0,
                evaluation_timestamp=snapshot.timestamp,
                symbol_info=symbol_info,
            )

        # ==============================================================
        # 9. FINAL SIGNAL
        # ==============================================================

        proposed_direction = (
            strategy_signal.signal.value
            if strategy_signal.signal
            != SignalType.NEUTRAL
            else None
        )

        final_signal = self.signal_engine.generate_signal(
            symbol=snapshot.symbol,
            asset_class=snapshot.asset_class,
            timeframe=snapshot.timeframe.value,
            timestamp=snapshot.timestamp,
            data_quality_status=data_quality_status,
            market_regime=regime.regime.value,
            strategy_name=strategy_signal.strategy_id.value,
            is_strategy_compatible=True,
            opportunity_result=opportunity_result,
            risk_proposal=risk_proposal,
            proposed_direction=proposed_direction,
        )

        return PipelineResult(
            signal=final_signal,
            data_quality_status=data_quality_status,
            data_quality_score=data_quality_score,
            features=features,
            regime=regime,
            strategy_signal=strategy_signal,
            opportunity_result=opportunity_result,
        )

    @staticmethod
    def _select_strategy_signal(
        signals: list[StrategySignal],
    ) -> Optional[StrategySignal]:
        """
        Sélection déterministe.

        Priorité :
        1. signaux BUY/SELL
        2. force la plus élevée
        3. StrategyID comme tie-breaker déterministe
        """

        actionable = [
            signal
            for signal in signals
            if signal.signal in (
                SignalType.BUY,
                SignalType.SELL,
            )
        ]

        if not actionable:
            return None

        actionable.sort(
            key=lambda signal: (
                -signal.strength,
                signal.strategy_id.value,
            )
        )

        return actionable[0]