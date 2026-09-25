from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone
from core.regime.services.engine import MarketRegimeEngine
from core.regime.domain.models import MarketRegime

router = APIRouter(prefix="/regime", tags=["Market Regime"])
engine = MarketRegimeEngine()

@router.get("/{symbol}", response_model=MarketRegime)
async def get_market_regime(
    symbol: str,
    asset_class: str = Query(..., description="forex, commodities, crypto, indices"),
    timeframe: str = Query("M15", description="M1, M5, M15, H1, D1")
):
    # Mock/Exemple d'intégration avec le Feature Engine de l'Étape 3
    fake_features = {
        "ema_20": 1.0850,
        "ema_50": 1.0810,
        "rsi_14": 58.4,
        "atr_14": 0.0012,
        "true_range": 0.0015
    }
    
    regime = engine.evaluate(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=datetime.now(timezone.utc),
        features=fake_features,
        data_quality="VALID"
    )
    return regime