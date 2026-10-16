from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.strategy.domain.enums import SignalType, StrategyID, StrategyStatus
from core.regime.domain.enums import TrendRegime


class StrategyMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: StrategyID
    name: str
    version: str = "1.0.0"
    description: str
    status: StrategyStatus = StrategyStatus.ENABLED
    compatible_regimes: List[str] = Field(default_factory=list)
    supported_asset_classes: List[str] = Field(
        default_factory=lambda: ["FOREX"]
    )
    supported_timeframes: List[str] = Field(
        default_factory=lambda: ["M15", "H1", "H4", "D1"]
    )
    inspiration: Optional[str] = None
    parameters: dict = Field(default_factory=dict)



class StrategySignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timeframe: str
    timestamp: datetime

    strategy_id: StrategyID
    signal: SignalType

    strength: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Conviction du signal (0.0 à 1.0)",
    )

    regime_context: TrendRegime

    evidence: List[str] = Field(
        default_factory=list,
        description="Raisons d'émission du signal",
    )

    suggested_sl_distance: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Distance de stop-loss exprimée dans l'unité de prix du symbole",
    )

    suggested_tp_distance: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Distance de take-profit exprimée dans l'unité de prix du symbole",
    )

    engine_version: str = "1.0.0"