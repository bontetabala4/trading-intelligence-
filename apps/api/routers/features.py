"""
GET /features/{symbol}
GET /features/{symbol}?timeframe=M15

Lit les bougies déjà persistées (Étape 2, MarketDataRepository), calcule
le MarketContext, et le retourne. Ne renvoie JAMAIS BUY/SELL/NO TRADE
(section 18) — uniquement des valeurs quantitatives et un statut de qualité.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from brokers.base.interface import Timeframe
from core.features.services.context_builder import MarketContextBuilder
from core.features.services.feature_engine import FeatureEngine, InsufficientDataError
from core.market.selection import AssetClass
from database.repositories.asset_repository import AssetRepository
from database.repositories.market_data_repository import MarketDataRepository
from database.session import get_db

router = APIRouter(tags=["features"])

# Nombre de bougies lues en base pour le calcul — suffisant pour EMA(200)
# avec une marge raisonnable, sans charger une quantité illimitée (cohérent
# avec la limite déjà appliquée sur /market-data en Étape 2).
_LOOKBACK_BARS = 300


@router.get("/features/{symbol}")
def get_features(
    symbol: str,
    asset_class: AssetClass = Query(...),
    timeframe: Timeframe = Query(default=Timeframe.M15),
    db: Session = Depends(get_db),
) -> dict:
    asset_repo = AssetRepository(db)
    asset = asset_repo.get_by_symbol(symbol.upper())
    if not asset:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Aucune donnée connue pour '{symbol}'. Collectez d'abord de "
                f"l'historique (POST /data/collect) avant de demander des features."
            ),
        )

    data_repo = MarketDataRepository(db)
    rows = data_repo.get_latest(asset.id, timeframe.value, limit=_LOOKBACK_BARS)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune donnée en base pour {symbol}/{timeframe.value}.",
        )

    bars = FeatureEngine.bars_from_market_data(rows)

    builder = MarketContextBuilder()
    try:
        context = builder.build(asset.symbol, asset_class, timeframe, bars)
    except InsufficientDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "status": "success",
        "symbol": context.symbol,
        "timeframe": context.timeframe.value,
        "timestamp": context.timestamp.isoformat(),
        "data_quality": context.data_quality.status.value,
        "price": context.price,
        "features": context.features.values,
    }
