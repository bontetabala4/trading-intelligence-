"""
GET /decision/{symbol} — chemin décisionnel unique (V1).
GET /decisions/{symbol} — historique persisté.

Broker live → ATIPPipeline → FinalSignal → PostgreSQL.
Pas d'exécution d'ordre.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.dependencies import get_broker
from brokers.base.interface import BrokerInterface, Timeframe
from configs.settings import get_settings
from core.decision.service import (
    DecisionServiceError,
    decision_record_to_dict,
    persist_decision,
    pipeline_result_to_dict,
    run_decision,
)
from core.market.selection import AssetClass
from database.repositories.decision_repository import DecisionRecordRepository
from database.session import get_db

logger = logging.getLogger("atip.api.decision")

router = APIRouter(tags=["decision"])


@router.get("/decision/{symbol}")
def get_decision(
    symbol: str,
    asset_class: AssetClass = Query(...),
    timeframe: Timeframe = Query(default=Timeframe.M15),
    lookback: int = Query(default=500, ge=50, le=5000),
    persist: bool = Query(default=True, description="Enregistrer la décision en base"),
    broker: BrokerInterface = Depends(get_broker),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = run_decision(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            broker=broker,
            lookback=lookback,
        )
    except DecisionServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    payload = pipeline_result_to_dict(result)
    record_id: int | None = None
    persisted = False

    if persist:
        try:
            record = persist_decision(db, result, get_settings())
            record_id = record.id
            persisted = True
        except Exception as exc:  # noqa: BLE001 — ne pas masquer la décision si DB down
            logger.exception("Échec persistance décision %s", result.signal.signal_id)
            payload["persistence_error"] = str(exc)

    return {
        "status": "success",
        "symbol": symbol.upper(),
        "timeframe": timeframe.value,
        "persisted": persisted,
        "record_id": record_id,
        "data": payload,
    }


@router.get("/decisions/{symbol}")
def list_decisions(
    symbol: str,
    timeframe: Timeframe | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    repo = DecisionRecordRepository(db)
    rows = repo.list_for_symbol(
        symbol=symbol,
        timeframe=timeframe.value if timeframe else None,
        limit=limit,
    )
    return {
        "status": "success",
        "symbol": symbol.upper(),
        "count": len(rows),
        "data": [decision_record_to_dict(row) for row in rows],
    }
