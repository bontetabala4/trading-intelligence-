"""
OpportunityValidator — Filtre et valide le statut final d'une opportunité
(VALID, REJECTED, UNCERTAIN) selon les règles de qualité et d'alignement.
"""
from typing import List
from core.opportunity.models import Opportunity, OpportunityResult, OpportunityScore, ValidationStatus


class OpportunityValidator:
    def __init__(
        self,
        min_data_quality: float = 0.70,
        valid_score_threshold: float = 65.0,
        uncertain_score_threshold: float = 45.0,
    ) -> None:
        self._min_dq = min_data_quality
        self._valid_thresh = valid_score_threshold
        self._uncertain_thresh = uncertain_score_threshold

    def validate(self, opportunity: Opportunity, score: OpportunityScore) -> OpportunityResult:
        reasons: List[str] = []

        # Gatekeeper 1 : Qualité des données
        if opportunity.data_quality_score < self._min_dq:
            reasons.append(
                f"Qualité des données insuffisante ({opportunity.data_quality_score:.2f} < {self._min_dq:.2f})"
            )
            return OpportunityResult(
                opportunity=opportunity,
                score=score,
                status=ValidationStatus.REJECTED,
                reasons=reasons,
            )

        # Gatekeeper 2 : Incompatibilité stratégique
        strat_eval = opportunity.evidence.get("strategy_evaluation", {})
        if not strat_eval.get("is_compatible", False):
            reasons.append("Stratégie déclarée incompatible avec le contexte actuel")
            return OpportunityResult(
                opportunity=opportunity,
                score=score,
                status=ValidationStatus.REJECTED,
                reasons=reasons,
            )

        # Gatekeeper 3 : Score global
        if score.total_score >= self._valid_thresh:
            status = ValidationStatus.VALID
            reasons.append(f"Score global ({score.total_score:.1f}) >= seuil de validation ({self._valid_thresh:.1f})")
        elif score.total_score >= self._uncertain_thresh:
            status = ValidationStatus.UNCERTAIN
            reasons.append(f"Score global ({score.total_score:.1f}) dans la zone d'incertitude [{self._uncertain_thresh:.1f}, {self._valid_thresh:.1f}[")
        else:
            status = ValidationStatus.REJECTED
            reasons.append(f"Score global ({score.total_score:.1f}) < seuil minimal ({self._uncertain_thresh:.1f})")

        return OpportunityResult(
            opportunity=opportunity,
            score=score,
            status=status,
            reasons=reasons,
        )