"""
Domain models pour le moteur de quantification et de validation d'opportunités (Étape 6).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ValidationStatus(str, Enum):
    VALID = "VALID"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


class OpportunityDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class Opportunity:
    symbol: str
    asset_class: str
    timeframe: str
    timestamp: datetime
    market_regime: str
    strategy_name: str
    direction: OpportunityDirection
    entry_reference: Optional[float] = None
    stop_reference: Optional[float] = None
    target_reference: Optional[float] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    data_quality_score: float = 1.0

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp doit être timezone-aware (UTC recommandé).")


@dataclass(frozen=True)
class OpportunityScore:
    total_score: float  # BORNÉ de 0.0 à 100.0
    sub_scores: Dict[str, float]
    explanation: Dict[str, str]

    def __post_init__(self) -> None:
        if not (0.0 <= self.total_score <= 100.0):
            raise ValueError(f"total_score doit être compris entre 0.0 et 100.0, reçu: {self.total_score}")


@dataclass(frozen=True)
class OpportunityResult:
    opportunity: Opportunity
    score: OpportunityScore
    status: ValidationStatus
    reasons: List[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))