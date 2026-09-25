"""
GET /market-data/{symbol}
GET /market-snapshot/{symbol}
GET /data-quality/{symbol}
POST /market-selection (validation de la sélection utilisateur)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from apps.api.dependencies import get_broker, get_market_observer
from brokers.base.interface import BrokerInterface, Timeframe
from core.market.observer import MarketObserverError
from core.market.selection import AssetClass, MarketSelection
from database.repositories.asset_repository import AssetRepository
from database.repositories.market_data_repository import MarketDataRepository
from database.session import get_db

router = APIRouter(tags=["market-data"])


@router.post("/market-selection")
def validate_market_selection(selection: dict) -> dict:
    """
    Valide une configuration MarketSelection sans effectuer de connexion broker.
    Rejette explicitement toute configuration incohérente (Pydantic).
    """
    try:
        parsed = MarketSelection(**selection)
    except ValidationError as exc:
        # exc.errors() peut contenir des objets Python non sérialisables (ex. ctx.error
        # est une ValueError brute) — on ne garde que les champs JSON-safe.
        safe_errors = [
            {"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=safe_errors) from exc

    return {
        "status": "success",
        "data": {
            "asset_class": parsed.asset_class.value,
            "symbol": parsed.symbol,
            "trading_style": parsed.trading_style.value,
            "timeframe": parsed.timeframe.value,
            "mode": parsed.mode.value,
            "style_matches_timeframe": parsed.style_matches_timeframe(),
        },
    }


@router.get("/market-data/{symbol}")
def get_market_data(
    symbol: str,
    timeframe: Timeframe = Query(default=Timeframe.M15),
    count: int = Query(default=200, ge=1, le=5000),
    broker: BrokerInterface = Depends(get_broker),
) -> dict:
    bars = broker.get_ohlcv(symbol.upper(), timeframe, count=count)
    if not bars:
        raise HTTPException(status_code=404, detail=f"Aucune donnée pour {symbol}/{timeframe.value}.")

    return {
        "status": "success",
        "symbol": symbol.upper(),
        "timeframe": timeframe.value,
        "data": {
            "bars": [
                {
                    "timestamp": b.timestamp.isoformat(),
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                    "spread": b.spread,
                }
                for b in bars
            ],
            "count": len(bars),
        },
    }


@router.get("/market-snapshot/{symbol}")
def get_market_snapshot(
    symbol: str,
    asset_class: AssetClass = Query(...),
    timeframe: Timeframe = Query(default=Timeframe.M15),
    persist: bool = Query(default=True, description="Enregistrer en DB si True."),
    observer=Depends(get_market_observer),
    db: Session = Depends(get_db),
) -> dict:
    try:
        snapshot = observer.build_snapshot(symbol.upper(), asset_class, timeframe)
    except MarketObserverError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if persist:
        asset_repo = AssetRepository(db)
        asset = asset_repo.get_or_create(snapshot.symbol, asset_class.value)

        data_repo = MarketDataRepository(db)
        data_repo.upsert_bar(
            asset_id=asset.id,
            timeframe=snapshot.timeframe.value,
            timestamp=snapshot.timestamp,
            open_=snapshot.open,
            high=snapshot.high,
            low=snapshot.low,
            close=snapshot.close,
            volume=snapshot.volume,
            spread=snapshot.spread,
        )
        data_repo.record_quality_event(
            asset_id=asset.id,
            timeframe=snapshot.timeframe.value,
            timestamp=snapshot.timestamp,
            status=snapshot.data_quality.status.value,
            score=snapshot.data_quality.score,
            issues=snapshot.data_quality.issues,
        )

    return {
        "status": "success",
        "symbol": snapshot.symbol,
        "timeframe": snapshot.timeframe.value,
        "data": {
            "asset_class": snapshot.asset_class.value,
            "timestamp": snapshot.timestamp.isoformat(),
            "price": snapshot.close,
            "spread": snapshot.spread,
            "data_quality": {
                "status": snapshot.data_quality.status.value,
                "score": snapshot.data_quality.score,
                "issues": snapshot.data_quality.issues,
            },
        },
    }


@router.get("/data-quality/{symbol}")
def get_data_quality(
    symbol: str,
    asset_class: AssetClass = Query(...),
    timeframe: Timeframe = Query(default=Timeframe.M15),
    observer=Depends(get_market_observer),
) -> dict:
    try:
        snapshot = observer.build_snapshot(symbol.upper(), asset_class, timeframe)
    except MarketObserverError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "status": "success",
        "symbol": snapshot.symbol,
        "timeframe": snapshot.timeframe.value,
        "data": {
            "status": snapshot.data_quality.status.value,
            "score": snapshot.data_quality.score,
            "issues": snapshot.data_quality.issues,
            "checked_at": snapshot.data_quality.checked_at.isoformat(),
        },
    }
