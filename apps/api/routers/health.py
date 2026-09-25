"""GET /health, GET /system/status"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.dependencies import get_broker
from apps.api.schemas.responses import SystemStatusResponse
from brokers.base.interface import BrokerInterface
from configs.settings import get_settings
from database.session import get_db

logger = logging.getLogger("atip.api.health")
router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "success", "data": {"application": "OK"}}


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status(
    db: Session = Depends(get_db),
    broker: BrokerInterface = Depends(get_broker),
) -> SystemStatusResponse:
    settings = get_settings()

    try:
        db.execute(text("SELECT 1"))
        db_status = "OK"
    except Exception as exc:  # noqa: BLE001 — on veut capturer toute erreur DB pour le statut
        logger.error("Database health check failed: %s", exc)
        db_status = "UNAVAILABLE"

    mt5_status = "CONNECTED" if broker.is_connected() else "DISCONNECTED"
    market_data_status = "AVAILABLE" if mt5_status == "CONNECTED" else "UNKNOWN"

    return SystemStatusResponse(
        application="OK",
        database=db_status,
        mt5=mt5_status,
        market_data=market_data_status,
        mode="ANALYSIS_ONLY" if not settings.trading_execution_enabled else "UNKNOWN",
    )
