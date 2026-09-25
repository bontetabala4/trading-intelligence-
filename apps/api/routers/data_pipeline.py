"""
GET /market-data/{symbol}/coverage
POST /data/collect   (protégé — désactivé par défaut, section 26)
GET /data/status
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.dependencies import get_collector
from brokers.base.interface import Timeframe
from configs.settings import get_settings
from core.market.selection import AssetClass
from database.repositories.asset_repository import AssetRepository
from database.repositories.market_data_repository import MarketDataRepository
from database.session import get_db

router = APIRouter(tags=["data-pipeline"])


class CollectRequest(BaseModel):
    symbol: str
    asset_class: AssetClass
    timeframe: Timeframe
    start: datetime | None = None  # absent => collecte incrémentale
    end: datetime | None = None


@router.get("/market-data/{symbol}/coverage")
def get_coverage(
    symbol: str,
    timeframe: Timeframe = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    asset_repo = AssetRepository(db)
    asset = asset_repo.get_by_symbol(symbol.upper())
    if not asset:
        raise HTTPException(
            status_code=404,
            detail=f"Aucune donnée connue pour '{symbol}' — aucune collecte n'a encore eu lieu.",
        )

    data_repo = MarketDataRepository(db)
    first_ts = data_repo.get_first_timestamp(asset.id, timeframe.value)
    last_ts = data_repo.get_last_timestamp(asset.id, timeframe.value)
    rows = data_repo.count(asset.id, timeframe.value)

    return {
        "status": "success",
        "symbol": asset.symbol,
        "timeframe": timeframe.value,
        "data": {
            "first_timestamp": first_ts.isoformat() if first_ts else None,
            "last_timestamp": last_ts.isoformat() if last_ts else None,
            "rows": rows,
        },
    }


@router.post("/data/collect")
def trigger_collection(
    request: CollectRequest,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    if not settings.data_collection_api_enabled:
        raise HTTPException(
            status_code=403,
            detail=(
                "L'API de collecte est désactivée par défaut "
                "(DATA_COLLECTION_API_ENABLED=false). Activez-la explicitement "
                "en environnement de développement pour l'utiliser."
            ),
        )

    collector = get_collector(db)

    if request.start is not None and request.end is not None:
        result = collector.collect(
            request.symbol.upper(), request.asset_class, request.timeframe,
            request.start, request.end,
        )
    else:
        result = collector.collect_incremental(
            request.symbol.upper(), request.asset_class, request.timeframe,
        )

    return {
        "status": "success",
        "symbol": result.symbol,
        "timeframe": result.timeframe.value,
        "data": {
            "collection_status": result.status.value,
            "range_start": result.range_start.isoformat() if result.range_start else None,
            "range_end": result.range_end.isoformat() if result.range_end else None,
            "rows_received": result.rows_received,
            "rows_inserted": result.rows_inserted,
            "rows_rejected": result.rows_rejected,
            "duration_ms": result.duration_ms,
            "errors": result.errors,
        },
    }


@router.get("/data/status")
def data_status(db: Session = Depends(get_db)) -> dict:
    data_repo = MarketDataRepository(db)
    events = data_repo.get_latest_ingestion_events(limit=20)

    return {
        "status": "success",
        "data": {
            "recent_ingestion_events": [
                {
                    "asset_id": e.asset_id,
                    "timeframe": e.timeframe,
                    "status": e.status,
                    "range_start": e.range_start.isoformat() if e.range_start else None,
                    "range_end": e.range_end.isoformat() if e.range_end else None,
                    "rows_processed": e.rows_processed,
                    "rows_inserted": e.rows_inserted,
                    "rows_rejected": e.rows_rejected,
                    "duration_ms": e.duration_ms,
                    "error_message": e.error_message,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ]
        },
    }
