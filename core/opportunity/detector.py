"""
OpportunityDetector — Identifie les opportunités brutes à partir d'un MarketContext
et des évaluations de stratégies sans appliquer de score final ni de validation.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.opportunity.models import Opportunity, OpportunityDirection


class OpportunityDetector:
    def detect(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        timestamp: datetime,
        market_regime: str,
        strategy_name: str,
        strategy_evaluation: Dict[str, Any],
        features: Dict[str, Any],
        data_quality_score: float = 1.0,
    ) -> Optional[Opportunity]:
        if timestamp.tzinfo is None:
            raise ValueError("timestamp doit être timezone-aware (UTC).")

        # Détection du signal de la stratégie
        signal = strategy_evaluation.get("signal", "NEUTRAL")
        if signal == "NEUTRAL" or not strategy_evaluation.get("is_compatible", False):
            return None

        direction = (
            OpportunityDirection.BULLISH
            if signal == "BUY"
            else OpportunityDirection.BEARISH
            if signal == "SELL"
            else OpportunityDirection.NEUTRAL
        )

        close_price = features.get("close") or features.get("close_price")
        atr = features.get("atr") or features.get("atr_14")

        entry_ref = float(close_price) if close_price is not None else None
        stop_ref = None
        target_ref = None

        if entry_ref is not None and atr is not None and atr > 0:
            mult = 1.5
            if direction == OpportunityDirection.BULLISH:
                stop_ref = entry_ref - (atr * mult)
                target_ref = entry_ref + (atr * mult * 2.0)
            elif direction == OpportunityDirection.BEARISH:
                stop_ref = entry_ref + (atr * mult)
                target_ref = entry_ref - (atr * mult * 2.0)

        evidence = {
            "strategy_evaluation": strategy_evaluation,
            "rsi": features.get("rsi"),
            "atr": atr,
            "trend_slope": features.get("trend_slope"),
            "bb_upper": features.get("bb_upper"),
            "bb_lower": features.get("bb_lower"),
        }

        return Opportunity(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            timestamp=timestamp,
            market_regime=market_regime,
            strategy_name=strategy_name,
            direction=direction,
            entry_reference=entry_ref,
            stop_reference=stop_ref,
            target_reference=target_ref,
            evidence=evidence,
            data_quality_score=data_quality_score,
        )