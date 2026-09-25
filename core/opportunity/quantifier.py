"""
OpportunityQuantifier — Calcule un score déterministe, explicable et borné (0–100)
représentant la qualité globale d'une opportunité détectée.
"""
from typing import Dict
from core.opportunity.models import Opportunity, OpportunityDirection, OpportunityScore


class OpportunityQuantifier:
    """
    Pondération du score (Total = 100 points) :
    - Data Quality: 15 pts
    - Strategy Alignment: 25 pts
    - Regime Alignment: 20 pts
    - Momentum Quality: 15 pts
    - Volatility Quality: 15 pts
    - Structure Quality: 10 pts
    """

    def quantify(self, opportunity: Opportunity) -> OpportunityScore:
        sub_scores: Dict[str, float] = {}
        explanations: Dict[str, str] = {}

        # 1. Data Quality (Max 15 pts)
        dq_score = max(0.0, min(1.0, opportunity.data_quality_score)) * 15.0
        sub_scores["data_quality"] = round(dq_score, 2)
        explanations["data_quality"] = f"Qualité des données à {opportunity.data_quality_score * 100:.1f}% ({dq_score:.1f}/15 pts)"

        # 2. Strategy Alignment (Max 25 pts)
        strat_eval = opportunity.evidence.get("strategy_evaluation", {})
        if strat_eval.get("is_compatible", False):
            strat_score = 25.0 if strat_eval.get("signal") in ("BUY", "SELL") else 12.5
        else:
            strat_score = 0.0
        sub_scores["strategy_alignment"] = round(strat_score, 2)
        explanations["strategy_alignment"] = f"Compatibilité stratégie: {strat_score:.1f}/25 pts"

        # 3. Regime Alignment (Max 20 pts)
        regime = opportunity.market_regime.upper()
        if "TREND" in regime and opportunity.direction in (OpportunityDirection.BULLISH, OpportunityDirection.BEARISH):
            regime_score = 20.0
        elif "RANGE" in regime or "RANGING" in regime:
            regime_score = 15.0 if opportunity.direction != OpportunityDirection.NEUTRAL else 5.0
        else:
            regime_score = 10.0
        sub_scores["regime_alignment"] = round(regime_score, 2)
        explanations["regime_alignment"] = f"Alignement régime '{regime}': {regime_score:.1f}/20 pts"

        # 4. Momentum Quality (Max 15 pts)
        rsi = opportunity.evidence.get("rsi")
        if rsi is not None:
            if opportunity.direction == OpportunityDirection.BULLISH and rsi > 45:
                mom_score = 15.0 if rsi < 70 else 7.5
            elif opportunity.direction == OpportunityDirection.BEARISH and rsi < 55:
                mom_score = 15.0 if rsi > 30 else 7.5
            else:
                mom_score = 5.0
            explanations["momentum"] = f"RSI à {rsi:.1f} en adéquation avec la direction: {mom_score:.1f}/15 pts"
        else:
            mom_score = 0.0
            explanations["momentum"] = "Donnée RSI absente (0.0/15 pts)"
        sub_scores["momentum_quality"] = round(mom_score, 2)

        # 5. Volatility Quality (Max 15 pts)
        atr = opportunity.evidence.get("atr")
        if atr is not None and atr > 0:
            vol_score = 15.0
            explanations["volatility"] = f"ATR présent ({atr:.4f}): 15.0/15 pts"
        else:
            vol_score = 0.0
            explanations["volatility"] = "Donnée ATR absente (0.0/15 pts)"
        sub_scores["volatility_quality"] = round(vol_score, 2)

        # 6. Structure Quality (Max 10 pts)
        if opportunity.entry_reference is not None and opportunity.stop_reference is not None:
            struct_score = 10.0
            explanations["structure"] = "Niveaux de prix et d'invalidation définis: 10.0/10 pts"
        else:
            struct_score = 0.0
            explanations["structure"] = "Niveaux d'invalidation absents (0.0/10 pts)"
        sub_scores["structure_quality"] = round(struct_score, 2)

        total = sum(sub_scores.values())
        total_bounded = max(0.0, min(100.0, total))

        return OpportunityScore(
            total_score=round(total_bounded, 2),
            sub_scores=sub_scores,
            explanation=explanations,
        )