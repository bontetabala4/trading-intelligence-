"""Enveloppes de réponse standardisées pour toute l'API."""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    status: str  # "success" | "error"
    symbol: str | None = None
    timeframe: str | None = None
    data: T | dict[str, Any] | None = None
    error: str | None = None


class MarketSnapshotResponse(BaseModel):
    symbol: str
    asset_class: str
    timeframe: str
    timestamp: str
    price: float
    spread: float | None
    data_quality: dict[str, Any]


class SystemStatusResponse(BaseModel):
    application: str
    database: str
    mt5: str
    market_data: str
    mode: str
