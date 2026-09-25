"""
Signal Engine Implementation for ATIP .

Ce module agrège les résultats d'opportunités, de risques et de qualité de données
pour générer des candidats de signaux et des signaux analytiques finaux déterministes.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid

from core.opportunity.models import OpportunityDirection, OpportunityResult, ValidationStatus
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

    # --------------------------------------------------------------------------
    # 1. Traitement Direct d'une Opportunité (Conversion Opportunité -> SignalCandidate)
    # --------------------------------------------------------------------------
    def process_opportunity(self, opportunity_result: OpportunityResult) -> SignalCandidate:
        """Consomme le résultat de l'Opportunity Engine (Étape 6)

        et émet un SignalCandidate analytique sans appel direct à l'exécution.
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
                confidence=opportunity_result.score.total_score / 100.0,
                rationale={
                    "status": opportunity_result.status.value,
                    "reasons": opportunity_result.reasons,
                    "score_breakdown": opportunity_result.score.sub_scores,
                },
                data_quality_score=opp.data_quality_score,
            )

        action = (
            SignalAction.BUY
            if opp.direction == OpportunityDirection.BULLISH
            else SignalAction.SELL
            if opp.direction == OpportunityDirection.BEARISH
            else SignalAction.NO_TRADE
        )

        return SignalCandidate(
            action=action,
            symbol=opp.symbol,
            asset_class=opp.asset_class,
            timeframe=opp.timeframe,
            timestamp=opp.timestamp,
            strategy_name=opp.strategy_name,
            market_regime=opp.market_regime,
            confidence=opportunity_result.score.total_score / 100.0,
            entry_price=opp.entry_reference,
            stop_loss=opp.stop_reference,
            take_profit=opp.target_reference,
            rationale={
                "status": opportunity_result.status.value,
                "reasons": opportunity_result.reasons,
                "score_explanation": opportunity_result.score.explanation,
                "evidence": opp.evidence,
            },
            data_quality_score=opp.data_quality_score,
        )

    # --------------------------------------------------------------------------
    # 2. Évaluation Globale Multi-Portes (Validation Complète du Pipeline -> FinalSignal)
    # --------------------------------------------------------------------------
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
        """Valide l'ensemble des filtres (Data Quality, Strategy Compatibility,

        Opportunity, Risk, Direction) pour émettre un FinalSignal.
        """
        reasons: List[str] = []
        evidence: Dict[str, Any] = {
            "market_regime": market_regime,
            "strategy": strategy_name,
            "data_quality": data_quality_status,
        }

        signal_id = str(uuid.uuid4())

        # Gate 1 : Data Quality
        if data_quality_status.upper() != "VALID":
            reasons.append(f"Data quality check failed with status: {data_quality_status}")
            return self._build_no_trade(
                signal_id, symbol, asset_class, timeframe, timestamp,
                market_regime, strategy_name, data_quality_status,
                NoTradeReason.INVALID_DATA, reasons, evidence,
                opportunity_result, risk_proposal
            )

        # Gate 2 : Strategy Compatibility
        if not is_strategy_compatible:
            reasons.append(f"Strategy {strategy_name} is incompatible with regime {market_regime}")
            return self._build_no_trade(
                signal_id, symbol, asset_class, timeframe, timestamp,
                market_regime, strategy_name, data_quality_status,
                NoTradeReason.STRATEGY_NOT_COMPATIBLE, reasons, evidence,
                opportunity_result, risk_proposal
            )

        # Gate 3 : Opportunity Assessment
        if opportunity_result is None:
            reasons.append("No opportunity result provided")
            return self._build_no_trade(
                signal_id, symbol, asset_class, timeframe, timestamp,
                market_regime, strategy_name, data_quality_status,
                NoTradeReason.OPPORTUNITY_REJECTED, reasons, evidence,
                opportunity_result, risk_proposal
            )

        opp_status = getattr(opportunity_result, "status", None)
        opp_status_str = str(opp_status.value) if hasattr(opp_status, "value") else str(opp_status)

        if opp_status_str == "REJECTED":
            reasons.append("Opportunity assessment rejected the setup")
            if hasattr(opportunity_result, "reasons"):
                reasons.extend(opportunity_result.reasons)
            return self._build_no_trade(
                signal_id, symbol, asset_class, timeframe, timestamp,
                market_regime, strategy_name, data_quality_status,
                NoTradeReason.OPPORTUNITY_REJECTED, reasons, evidence,
                opportunity_result, risk_proposal
            )

        if opp_status_str == "UNCERTAIN":
            reasons.append("Opportunity assessment flagged setup as uncertain")
            return self._build_no_trade(
                signal_id, symbol, asset_class, timeframe, timestamp,
                market_regime, strategy_name, data_quality_status,
                NoTradeReason.OPPORTUNITY_UNCERTAIN, reasons, evidence,
                opportunity_result, risk_proposal
            )

        # Gate 4 : Risk Assessment
        if risk_proposal is None:
            reasons.append("No risk proposal provided")
            return self._build_no_trade(
                signal_id, symbol, asset_class, timeframe, timestamp,
                market_regime, strategy_name, data_quality_status,
                NoTradeReason.RISK_REJECTED, reasons, evidence,
                opportunity_result, risk_proposal
            )

        risk_status = getattr(risk_proposal, "status", None)
        risk_status_str = str(risk_status.value) if hasattr(risk_status, "value") else str(risk_status)

        if risk_status_str == "REJECTED":
            reason_msg = getattr(risk_proposal, "reject_reason", "Risk assessment rejected")
            reasons.append(f"Risk rejected: {reason_msg}")
            return self._build_no_trade(
                signal_id, symbol, asset_class, timeframe, timestamp,
                market_regime, strategy_name, data_quality_status,
                NoTradeReason.RISK_REJECTED, reasons, evidence,
                opportunity_result, risk_proposal
            )

        if risk_status_str == "REQUIRES_REVIEW":
            reasons.append("Risk assessment requires human manual review")
            return self._build_no_trade(
                signal_id, symbol, asset_class, timeframe, timestamp,
                market_regime, strategy_name, data_quality_status,
                NoTradeReason.RISK_REVIEW_REQUIRED, reasons, evidence,
                opportunity_result, risk_proposal
            )

        # Gate 5 : Direction Gate
        direction_clean = proposed_direction.upper() if proposed_direction else ""
        if direction_clean in ("BUY", "BULLISH"):
            final_direction = FinalSignalDirection.BUY
        elif direction_clean in ("SELL", "BEARISH"):
            final_direction = FinalSignalDirection.SELL
        else:
            reasons.append("Direction missing or neutral")
            return self._build_no_trade(
                signal_id, symbol, asset_class, timeframe, timestamp,
                market_regime, strategy_name, data_quality_status,
                NoTradeReason.MISSING_DIRECTION, reasons, evidence,
                opportunity_result, risk_proposal
            )

        # Extraction des références de prix
        entry_ref = getattr(opportunity_result, "entry_reference", None)
        if entry_ref is None and hasattr(opportunity_result, "opportunity"):
            entry_ref = getattr(opportunity_result.opportunity, "entry_reference", None)

        stop_ref = getattr(risk_proposal, "stop_loss", None)
        target_ref = getattr(risk_proposal, "take_profit", None)

        opp_score = 0.0
        if hasattr(opportunity_result, "score"):
            opp_score = getattr(opportunity_result.score, "total_score", 0.0)

        reasons.extend([
            f"Market regime: {market_regime}",
            f"Strategy: {strategy_name}",
            f"Opportunity: {opp_status_str}",
            f"Risk: {risk_status_str}",
            f"Data quality: {data_quality_status}"
        ])

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
            risk_score=getattr(risk_proposal, "risk_score", 0.0),
            data_quality_status=data_quality_status,
            reasons=reasons,
            evidence=evidence,
            entry_reference=entry_ref,
            stop_reference=stop_ref,
            target_reference=target_ref,
            risk_reward=getattr(risk_proposal, "risk_reward", None),
            signal_version=self.signal_version,
        )

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
        if opportunity_result:
            st = getattr(opportunity_result, "status", "N/A")
            opp_status_str = str(st.value) if hasattr(st, "value") else str(st)
            if hasattr(opportunity_result, "score"):
                opp_score = getattr(opportunity_result.score, "total_score", 0.0)

        risk_status_str = "N/A"
        risk_score = 0.0
        if risk_proposal:
            st = getattr(risk_proposal, "status", "N/A")
            risk_status_str = str(st.value) if hasattr(st, "value") else str(st)
            risk_score = getattr(risk_proposal, "risk_score", 0.0)

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