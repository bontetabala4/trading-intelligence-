from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict, Field
from core.regime.domain.enums import TrendRegime, VolatilityState, ConfidenceLevel

class MarketRegime(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    timestamp: datetime
    regime: TrendRegime
    volatility_state: VolatilityState
    strength: float = Field(..., ge=0.0, le=1.0, description="Force/Confiance du classifieur (non-probabiliste)")
    confidence: ConfidenceLevel
    evidence: List[str] = Field(default_factory=list, description="Raisons explicables de la classification")
    data_quality: str
    engine_version: str = "1.0.0"