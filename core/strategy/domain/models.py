from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from core.strategy.domain.enums import SignalType, StrategyID
from core.regime.domain.enums import TrendRegime

class StrategySignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    timestamp: datetime
    strategy_id: StrategyID
    signal: SignalType
    strength: float = Field(..., ge=0.0, le=1.0, description="Conviction du signal (0.0 à 1.0)")
    regime_context: TrendRegime
    evidence: List[str] = Field(default_factory=list, description="Raisons d'émission du signal")
    suggested_sl_pips: Optional[float] = None
    suggested_tp_pips: Optional[float] = None
    engine_version: str = "1.0.0"