from datetime import datetime, timezone
import logging
import uuid
from typing import Any, Dict, List, Optional

import pandas as pd

from core.opportunity.models import (
    OpportunityDirection,
    OpportunityResult,
    ValidationStatus,
)
from core.signal.domain import (
    FinalSignal,
    FinalSignalDirection,
    NoTradeReason,
    SignalAction,
    SignalCandidate,
)

logger = logging.getLogger("atip.signal_engine")


class SignalEngine:
    def __init__(self, signal_version: str = "1.0.0"):
        self.signal_version = signal_version

    # ------------------------------------------------------------------
    # API historique / compatibilité
    # ------------------------------------------------------------------

    def process(
        self,
        history: Any,
        symbol: str = "EURUSD",
        timeframe: str = "M15",
    ) -> Dict[str, Any]:
      
        if not isinstance(history, pd.DataFrame) or len(history) < 2:
            return {
                "signal": "NO_TRADE",
                "regime": "UNCERTAIN",
                "score": 0.0,
                "risk_levels": {
                    "stop_price": None,
                    "target_price": None,
                },
            }

        required_columns = {"close", "high", "low"}

        if not required_columns.issubset(history.columns):
            return {
                "signal": "NO_TRADE",
                "regime": "UNCERTAIN",
                "score": 0.0,
                "risk_levels": {
                    "stop_price": None,
                    "target_price": None,
                },
            }

       
        close = history["close"]
        high = history["high"]
        low = history["low"]

        last_close = float(close.iloc[-1])

        ema_20 = (
            float(close.ewm(span=20, adjust=False).mean().iloc[-1])
            if len(close) >= 20
            else last_close
        )

        ema_50 = (
            float(close.ewm(span=50, adjust=False).mean().iloc[-1])
            if len(close) >= 50
            else last_close
        )

        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)

        atr_14 = (
            float(tr.rolling(14).mean().iloc[-1])
            if len(tr) >= 14
            else 0.0015
        )

        if pd.isna(atr_14) or atr_14 <= 0:
            atr_14 = 0.0015

        true_range = (
            float(tr.iloc[-1])
            if not pd.isna(tr.iloc[-1])
            else atr_14
        )

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = (
            float(gain.rolling(14).mean().iloc[-1])
            if len(delta) >= 14
            else 0.0
        )

        avg_loss = (
            float(loss.rolling(14).mean().iloc[-1])
            if len(delta) >= 14
            else 0.0
        )

        if (
            pd.isna(avg_gain)
            or pd.isna(avg_loss)
            or (avg_gain + avg_loss) == 0
        ):
            rsi_14 = 50.0
        else:
            rs = avg_gain / (avg_loss + 1e-9)
            rsi_14 = float(
                100.0 - (100.0 / (1.0 + rs))
            )

        # --------------------------------------------------------------
        # Timestamp
        # --------------------------------------------------------------

        ts = (
            history["timestamp"].iloc[-1]
            if "timestamp" in history.columns
            else datetime.now(timezone.utc)
        )

        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()

        if not isinstance(ts, datetime):
            ts = datetime.now(timezone.utc)

        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # --------------------------------------------------------------
        # Features
        # --------------------------------------------------------------

        features = {
            "ema_20": ema_20,
            "ema_50": ema_50,
            "rsi_14": rsi_14,
            "atr_14": atr_14,
            "true_range": true_range,
            "close": last_close,
        }

        # --------------------------------------------------------------
        # Market Regime
        # --------------------------------------------------------------

        from core.regime.services.engine import MarketRegimeEngine

        regime_engine = MarketRegimeEngine()

        regime = regime_engine.evaluate(
            symbol,
            timeframe,
            ts,
            features,
            data_quality="VALID",
        )

        regime_str = regime.regime.value

        # --------------------------------------------------------------
        # Strategy
        # --------------------------------------------------------------

        from core.strategy.services.engine import StrategyEngine

        strategy_engine = StrategyEngine()

        strategy_signals = strategy_engine.evaluate_all(
            regime,
            features,
        )

        active_strat = (
            strategy_signals[0].strategy_id
            if strategy_signals
            else "Trend Following"
        )

        strat_sig = (
            strategy_signals[0].signal.value
            if strategy_signals
            else "HOLD"
        )

        is_compat = bool(strategy_signals)

        # --------------------------------------------------------------
        # Opportunity
        # --------------------------------------------------------------

        from core.opportunity.detector import OpportunityDetector
        from core.opportunity.quantifier import OpportunityQuantifier
        from core.opportunity.validator import OpportunityValidator

        opp_detector = OpportunityDetector()
        opp_quantifier = OpportunityQuantifier()
        opp_validator = OpportunityValidator()

        opp = opp_detector.detect(
            symbol=symbol,
            asset_class="FOREX",
            timeframe=timeframe,
            timestamp=ts,
            market_regime=regime_str,
            strategy_name=active_strat,
            strategy_evaluation={
                "is_compatible": is_compat,
                "signal": strat_sig,
            },
            features=features,
            data_quality_score=1.0,
        )

        opp_result = None

        if opp is not None:
            opp_score = opp_quantifier.quantify(opp)
            opp_result = opp_validator.validate(
                opp,
                opp_score,
            )

        # --------------------------------------------------------------
        # Risk
        # --------------------------------------------------------------

        from core.risk.services.engine import RiskEngine
        from core.risk.domain.models import AccountState

        risk_engine = RiskEngine()

        account_state = AccountState(
            account_id="ACC_PAPER",
            balance=10000.0,
            equity=10000.0,
            used_margin=0.0,
            free_margin=10000.0,
            current_daily_drawdown=0.0,
            max_daily_drawdown_limit=500.0,
            max_open_positions=5,
            current_open_positions=0,
            active_positions=[],
            closed_trades_today=[],
        )

        strat_model_signal = (
            strategy_signals[0]
            if strategy_signals
            else None
        )

        risk_proposal = None

        if (
            strat_model_signal
            and strat_model_signal.signal.value in ("BUY", "SELL")
        ):
            risk_proposal = risk_engine.evaluate_signal(
                strat_model_signal,
                account_state,
                last_close,
            )

        # --------------------------------------------------------------
        # Final Signal
        # --------------------------------------------------------------

        proposed_dir = (
            strat_sig
            if strat_sig in ("BUY", "SELL")
            else None
        )

        final_sig = self.generate_signal(
            symbol=symbol,
            asset_class="FOREX",
            timeframe=timeframe,
            timestamp=ts,
            data_quality_status="VALID",
            market_regime=regime_str,
            strategy_name=active_strat,
            is_strategy_compatible=is_compat,
            opportunity_result=opp_result,
            risk_proposal=risk_proposal,
            proposed_direction=proposed_dir,
        )

        stop_price = (
            getattr(risk_proposal, "stop_loss", None)
            if risk_proposal
            else None
        )

        target_price = (
            getattr(risk_proposal, "take_profit", None)
            if risk_proposal
            else None
        )

        return {
            "signal": final_sig.direction.value,
            "regime": regime_str,
            "score": final_sig.opportunity_score,
            "risk_levels": {
                "stop_price": stop_price,
                "target_price": target_price,
            },
            "final_signal": final_sig,
        }

    def process_bar(self, *args, **kwargs) -> Any:
        return self.process(*args, **kwargs)

    def evaluate(self, *args, **kwargs) -> Any:
        return self.process(*args, **kwargs)

    # ------------------------------------------------------------------
    # Opportunity -> SignalCandidate
    # ------------------------------------------------------------------

    def process_opportunity(
        self,
        opportunity_result: OpportunityResult,
    ) -> SignalCandidate:
        """
        Convertit un résultat d'opportunité en SignalCandidate.

        Aucun accès à l'exécution d'ordre.
        """

        opp = opportunity_result.opportunity

        if opportunity_result.status != ValidationStatus.VALID:
            return SignalCandidate(
                action=SignalAction.NO_TRADE,
                symbol=opp.symbol,
                asset_class=opp.asset_class,
                timeframe=opp.timeframe,
                timestamp=opp.timestamp,
                strategy_name=opp.strategy_name,
                market_regime=opp.market_regime,
                confidence=(
                    opportunity_result.score.total_score / 100.0
                ),
                rationale={
                    "status": opportunity_result.status.value,
                    "reasons": opportunity_result.reasons,
                    "score_breakdown": (
                        opportunity_result.score.sub_scores
                    ),
                },
                data_quality_score=opp.data_quality_score,
            )

        if opp.direction == OpportunityDirection.BULLISH:
            action = SignalAction.BUY

        elif opp.direction == OpportunityDirection.BEARISH:
            action = SignalAction.SELL

        else:
            action = SignalAction.NO_TRADE

        return SignalCandidate(
            action=action,
            symbol=opp.symbol,
            asset_class=opp.asset_class,
            timeframe=opp.timeframe,
            timestamp=opp.timestamp,
            strategy_name=opp.strategy_name,
            market_regime=opp.market_regime,
            confidence=(
                opportunity_result.score.total_score / 100.0
            ),
            entry_price=opp.entry_reference,
            stop_loss=opp.stop_reference,
            take_profit=opp.target_reference,
            rationale={
                "status": opportunity_result.status.value,
                "reasons": opportunity_result.reasons,
                "score_explanation": (
                    opportunity_result.score.explanation
                ),
                "evidence": opp.evidence,
            },
            data_quality_score=opp.data_quality_score,
        )

    # ------------------------------------------------------------------
    # Final Signal
    # ------------------------------------------------------------------

    def generate_signal(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        timestamp: datetime,
        data_quality_status: str,
        market_regime: str,
        strategy_name: str,
        is_strategy_compatible: bool,
        opportunity_result: Optional[Any] = None,
        risk_proposal: Optional[Any] = None,
        proposed_direction: Optional[str] = None,
    ) -> FinalSignal:
        """
        Applique les cinq gates de validation :

        1. Data Quality
        2. Strategy Compatibility
        3. Opportunity
        4. Risk
        5. Direction
        """

        reasons: List[str] = []

        evidence: Dict[str, Any] = {
            "market_regime": market_regime,
            "strategy": strategy_name,
            "data_quality": data_quality_status,
        }

        signal_id = self._build_deterministic_signal_id(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
        )

        # --------------------------------------------------------------
        # Gate 1 — Data Quality
        # --------------------------------------------------------------

        if data_quality_status.upper() != "VALID":
            reasons.append(
                "Data quality check failed with status: "
                f"{data_quality_status}"
            )

            return self._build_no_trade(
                signal_id,
                symbol,
                asset_class,
                timeframe,
                timestamp,
                market_regime,
                strategy_name,
                data_quality_status,
                NoTradeReason.INVALID_DATA,
                reasons,
                evidence,
                opportunity_result,
                risk_proposal,
            )

        # --------------------------------------------------------------
        # Gate 2 — Strategy Compatibility
        # --------------------------------------------------------------

        if not is_strategy_compatible:
            reasons.append(
                f"Strategy {strategy_name} is incompatible "
                f"with regime {market_regime}"
            )

            return self._build_no_trade(
                signal_id,
                symbol,
                asset_class,
                timeframe,
                timestamp,
                market_regime,
                strategy_name,
                data_quality_status,
                NoTradeReason.STRATEGY_NOT_COMPATIBLE,
                reasons,
                evidence,
                opportunity_result,
                risk_proposal,
            )

        # --------------------------------------------------------------
        # Gate 3 — Opportunity
        # --------------------------------------------------------------

        if opportunity_result is None:
            reasons.append(
                "No opportunity result provided"
            )

            return self._build_no_trade(
                signal_id,
                symbol,
                asset_class,
                timeframe,
                timestamp,
                market_regime,
                strategy_name,
                data_quality_status,
                NoTradeReason.OPPORTUNITY_REJECTED,
                reasons,
                evidence,
                opportunity_result,
                risk_proposal,
            )

        opp_status = getattr(
            opportunity_result,
            "status",
            None,
        )

        opp_status_str = (
            str(opp_status.value)
            if hasattr(opp_status, "value")
            else str(opp_status)
        )

        if opp_status_str == "REJECTED":
            reasons.append(
                "Opportunity assessment rejected the setup"
            )

            if hasattr(opportunity_result, "reasons"):
                reasons.extend(
                    opportunity_result.reasons
                )

            return self._build_no_trade(
                signal_id,
                symbol,
                asset_class,
                timeframe,
                timestamp,
                market_regime,
                strategy_name,
                data_quality_status,
                NoTradeReason.OPPORTUNITY_REJECTED,
                reasons,
                evidence,
                opportunity_result,
                risk_proposal,
            )

        if opp_status_str == "UNCERTAIN":
            reasons.append(
                "Opportunity assessment flagged setup as uncertain"
            )

            return self._build_no_trade(
                signal_id,
                symbol,
                asset_class,
                timeframe,
                timestamp,
                market_regime,
                strategy_name,
                data_quality_status,
                NoTradeReason.OPPORTUNITY_UNCERTAIN,
                reasons,
                evidence,
                opportunity_result,
                risk_proposal,
            )

        # --------------------------------------------------------------
        # Gate 4 — Risk
        # --------------------------------------------------------------

        if risk_proposal is None:
            reasons.append(
                "No risk proposal provided"
            )

            return self._build_no_trade(
                signal_id,
                symbol,
                asset_class,
                timeframe,
                timestamp,
                market_regime,
                strategy_name,
                data_quality_status,
                NoTradeReason.RISK_REJECTED,
                reasons,
                evidence,
                opportunity_result,
                risk_proposal,
            )

        risk_status = getattr(
            risk_proposal,
            "status",
            None,
        )

        risk_status_str = (
            str(risk_status.value)
            if hasattr(risk_status, "value")
            else str(risk_status)
        )

        if risk_status_str == "REJECTED":
            reason_msg = getattr(
                risk_proposal,
                "reject_reason",
                "Risk assessment rejected",
            )

            reasons.append(
                f"Risk rejected: {reason_msg}"
            )

            return self._build_no_trade(
                signal_id,
                symbol,
                asset_class,
                timeframe,
                timestamp,
                market_regime,
                strategy_name,
                data_quality_status,
                NoTradeReason.RISK_REJECTED,
                reasons,
                evidence,
                opportunity_result,
                risk_proposal,
            )

        if risk_status_str == "REQUIRES_REVIEW":
            reasons.append(
                "Risk assessment requires human manual review"
            )

            return self._build_no_trade(
                signal_id,
                symbol,
                asset_class,
                timeframe,
                timestamp,
                market_regime,
                strategy_name,
                data_quality_status,
                NoTradeReason.RISK_REVIEW_REQUIRED,
                reasons,
                evidence,
                opportunity_result,
                risk_proposal,
            )

        # --------------------------------------------------------------
        # Gate 5 — Direction
        # --------------------------------------------------------------

        direction_clean = (
            proposed_direction.upper()
            if proposed_direction
            else ""
        )

        if direction_clean in ("BUY", "BULLISH"):
            final_direction = FinalSignalDirection.BUY

        elif direction_clean in ("SELL", "BEARISH"):
            final_direction = FinalSignalDirection.SELL

        else:
            reasons.append(
                "Direction missing or neutral"
            )

            return self._build_no_trade(
                signal_id,
                symbol,
                asset_class,
                timeframe,
                timestamp,
                market_regime,
                strategy_name,
                data_quality_status,
                NoTradeReason.MISSING_DIRECTION,
                reasons,
                evidence,
                opportunity_result,
                risk_proposal,
            )

        # --------------------------------------------------------------
        # Price references
        # --------------------------------------------------------------

        entry_ref = getattr(
            opportunity_result,
            "entry_reference",
            None,
        )

        if (
            entry_ref is None
            and hasattr(opportunity_result, "opportunity")
        ):
            entry_ref = getattr(
                opportunity_result.opportunity,
                "entry_reference",
                None,
            )

        stop_ref = getattr(
            risk_proposal,
            "stop_loss",
            None,
        )

        target_ref = getattr(
            risk_proposal,
            "take_profit",
            None,
        )

        opp_score = 0.0

        if hasattr(opportunity_result, "score"):
            opp_score = getattr(
                opportunity_result.score,
                "total_score",
                0.0,
            )

        reasons.extend(
            [
                f"Market regime: {market_regime}",
                f"Strategy: {strategy_name}",
                f"Opportunity: {opp_status_str}",
                f"Risk: {risk_status_str}",
                f"Data quality: {data_quality_status}",
            ]
        )

        return FinalSignal(
            signal_id=signal_id,
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            timestamp=timestamp,
            direction=final_direction,
            no_trade_reason=NoTradeReason.NONE,
            strategy=strategy_name,
            market_regime=market_regime,
            opportunity_status=opp_status_str,
            opportunity_score=opp_score,
            risk_status=risk_status_str,
            risk_score=getattr(
                risk_proposal,
                "risk_score",
                0.0,
            ),
            data_quality_status=data_quality_status,
            reasons=reasons,
            evidence=evidence,
            entry_reference=entry_ref,
            stop_reference=stop_ref,
            target_reference=target_ref,
            risk_reward=getattr(
                risk_proposal,
                "risk_reward",
                None,
            ),
            signal_version=self.signal_version,
        )

    # ------------------------------------------------------------------
    # Deterministic ID
    # ------------------------------------------------------------------

    def _build_deterministic_signal_id(
        self,
        symbol: str,
        timeframe: str,
        timestamp: datetime,
    ) -> str:
        """
        Construit un identifiant stable pour un même
        symbole + timeframe + timestamp.
        """

        raw = (
            f"{symbol}|"
            f"{timeframe}|"
            f"{timestamp.isoformat()}"
        )

        return str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                raw,
            )
        )

    # ------------------------------------------------------------------
    # NO_TRADE builder
    # ------------------------------------------------------------------

    def _build_no_trade(
        self,
        signal_id: str,
        symbol: str,
        asset_class: str,
        timeframe: str,
        timestamp: datetime,
        market_regime: str,
        strategy_name: str,
        data_quality_status: str,
        reason: NoTradeReason,
        reasons: List[str],
        evidence: Dict[str, Any],
        opportunity_result: Optional[Any],
        risk_proposal: Optional[Any],
    ) -> FinalSignal:

        opp_status_str = "N/A"
        opp_score = 0.0

        if opportunity_result is not None:
            st = getattr(
                opportunity_result,
                "status",
                "N/A",
            )

            opp_status_str = (
                str(st.value)
                if hasattr(st, "value")
                else str(st)
            )

            if hasattr(opportunity_result, "score"):
                opp_score = getattr(
                    opportunity_result.score,
                    "total_score",
                    0.0,
                )

        risk_status_str = "N/A"
        risk_score = 0.0

        if risk_proposal is not None:
            st = getattr(
                risk_proposal,
                "status",
                "N/A",
            )

            risk_status_str = (
                str(st.value)
                if hasattr(st, "value")
                else str(st)
            )

            risk_score = getattr(
                risk_proposal,
                "risk_score",
                0.0,
            )

        return FinalSignal(
            signal_id=signal_id,
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            timestamp=timestamp,
            direction=FinalSignalDirection.NO_TRADE,
            no_trade_reason=reason,
            strategy=strategy_name,
            market_regime=market_regime,
            opportunity_status=opp_status_str,
            opportunity_score=opp_score,
            risk_status=risk_status_str,
            risk_score=risk_score,
            data_quality_status=data_quality_status,
            reasons=reasons,
            evidence=evidence,
            signal_version=self.signal_version,
        )