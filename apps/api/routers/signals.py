from fastapi import APIRouter, Query
from datetime import datetime, timezone
from typing import List
from core.regime.services.engine import MarketRegimeEngine
from core.strategy.services.StrategyEngine import StrategyEngine
from core.strategy.domain.models import StrategySignal

router = APIRouter(prefix="/signals", tags=["Trading Signals"])

regime_engine = MarketRegimeEngine()
strategy_engine = StrategyEngine()

@router.get("/{symbol}", response_model=List[StrategySignal])
async def get_signals(
    symbol: str,
    timeframe: str = Query("M15", description="M1, M5, M15, H1, D1")
):
    fake_features = {
        "ema_20": 1.0850,
        "ema_50": 1.0810,
        "rsi_14": 58.4,
        "atr_14": 0.0012,
        "true_range": 0.0015
    }

    now = datetime.now(timezone.utc)
    regime = regime_engine.evaluate(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=now,
        features=fake_features,
        data_quality="VALID"
    )

    return strategy_engine.evaluate_all(regime, fake_features)