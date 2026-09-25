"""MarketSnapshot — DTO factuel. Ne contient jamais de signal BUY/SELL."""
from dataclasses import dataclass
from datetime import datetime

from brokers.base.interface import Timeframe
from core.data.quality_engine import DataQualityReport
from core.market.selection import AssetClass


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    asset_class: AssetClass
    timeframe: Timeframe
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    spread: float | None
    data_quality: DataQualityReport
