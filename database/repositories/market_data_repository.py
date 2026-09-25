"""
Repository pour MarketData, DataQualityEvent et IngestionEvent.

Étape 1 : upsert_bar() (chemin observation instantanée / market-snapshot).
Étape 2 : save_batch() (chemin collecte historique), méthodes de lecture par
plage, couverture, et suivi des événements de collecte.
"""
import json
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from brokers.base.interface import OHLCVBar
from database.models import DataQualityEvent, IngestionEvent, MarketData


class MarketDataRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # --- Étape 1 : conservé tel quel (chemin market-snapshot) ---

    def upsert_bar(
        self,
        asset_id: int,
        timeframe: str,
        timestamp: datetime,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        spread: float | None = None,
    ) -> None:
        """
        Upsert basé sur la contrainte UNIQUE(asset_id, timeframe, timestamp)
        pour éviter la duplication de bougies en cas de ré-ingestion.
        """
        stmt = insert(MarketData).values(
            asset_id=asset_id,
            timeframe=timeframe,
            timestamp=timestamp,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            spread=spread,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_market_data_bar",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "spread": stmt.excluded.spread,
            },
        )
        self._db.execute(stmt)
        self._db.commit()

    def record_quality_event(
        self,
        asset_id: int,
        timeframe: str,
        timestamp: datetime,
        status: str,
        score: float,
        issues: list[str],
    ) -> DataQualityEvent:
        event = DataQualityEvent(
            asset_id=asset_id,
            timeframe=timeframe,
            timestamp=timestamp,
            status=status,
            score=score,
            issues=json.dumps(issues),
        )
        self._db.add(event)
        self._db.commit()
        self._db.refresh(event)
        return event

    # --- Étape 2 : collecte historique ---

    def save_batch(
        self, asset_id: int, timeframe: str, bars: list[OHLCVBar], source: str
    ) -> int:
        """
        Insertion idempotente en lot via ON CONFLICT DO UPDATE sur la même
        contrainte unique que upsert_bar(). Retourne le nombre de lignes
        effectivement traitées.
        """
        if not bars:
            return 0

        values = []
        for bar in bars:
            # Compatibilité Pydantic / dataclass / objet
            if hasattr(bar, "model_dump"):
                bar_dict = bar.model_dump()
            elif hasattr(bar, "__dict__"):
                bar_dict = bar.__dict__
            else:
                bar_dict = bar

            values.append(
                {
                    "asset_id": asset_id,
                    "timeframe": timeframe,
                    "timestamp": bar_dict.get("timestamp"),
                    "open": bar_dict.get("open"),
                    "high": bar_dict.get("high"),
                    "low": bar_dict.get("low"),
                    "close": bar_dict.get("close"),
                    "volume": bar_dict.get("volume", 0.0),
                    "spread": bar_dict.get("spread"),
                    "tick_volume": bar_dict.get("tick_volume"),
                    "real_volume": bar_dict.get("real_volume"),
                    "source": source,
                }
            )

        stmt = insert(MarketData).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_market_data_bar",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "spread": stmt.excluded.spread,
                "tick_volume": stmt.excluded.tick_volume,
                "real_volume": stmt.excluded.real_volume,
                "source": stmt.excluded.source,
            },
        )
        self._db.execute(stmt)
        self._db.commit()
        return len(bars)

    def get_range(
        self, asset_id: int, timeframe: str, start: datetime, end: datetime, limit: int = 5000
    ) -> list[MarketData]:
        stmt = (
            select(MarketData)
            .where(
                MarketData.asset_id == asset_id,
                MarketData.timeframe == timeframe,
                MarketData.timestamp >= start,
                MarketData.timestamp <= end,
            )
            .order_by(MarketData.timestamp.asc())
            .limit(limit)
        )
        return list(self._db.execute(stmt).scalars().all())

    def get_latest(self, asset_id: int, timeframe: str, limit: int = 500) -> list[MarketData]:
        stmt = (
            select(MarketData)
            .where(MarketData.asset_id == asset_id, MarketData.timeframe == timeframe)
            .order_by(MarketData.timestamp.desc())
            .limit(limit)
        )
        rows = list(self._db.execute(stmt).scalars().all())
        return list(reversed(rows))  # ordre chronologique croissant

    def get_first_timestamp(self, asset_id: int, timeframe: str) -> datetime | None:
        stmt = select(func.min(MarketData.timestamp)).where(
            MarketData.asset_id == asset_id, MarketData.timeframe == timeframe
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def get_last_timestamp(self, asset_id: int, timeframe: str) -> datetime | None:
        stmt = select(func.max(MarketData.timestamp)).where(
            MarketData.asset_id == asset_id, MarketData.timeframe == timeframe
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def count(self, asset_id: int, timeframe: str) -> int:
        stmt = select(func.count(MarketData.id)).where(
            MarketData.asset_id == asset_id, MarketData.timeframe == timeframe
        )
        return self._db.execute(stmt).scalar_one()

    def exists(self, asset_id: int, timeframe: str, timestamp: datetime) -> bool:
        stmt = select(MarketData.id).where(
            MarketData.asset_id == asset_id,
            MarketData.timeframe == timeframe,
            MarketData.timestamp == timestamp,
        )
        return self._db.execute(stmt).first() is not None

    def delete_range(self, asset_id: int, timeframe: str, start: datetime, end: datetime) -> int:
        stmt = delete(MarketData).where(
            MarketData.asset_id == asset_id,
            MarketData.timeframe == timeframe,
            MarketData.timestamp >= start,
            MarketData.timestamp <= end,
        )
        result = self._db.execute(stmt)
        self._db.commit()
        return result.rowcount or 0

    # --- Étape 2 : suivi de collecte ---

    def record_ingestion_event(
        self,
        asset_id: int,
        timeframe: str,
        status: str,
        range_start: datetime | None,
        range_end: datetime | None,
        rows_processed: int,
        rows_inserted: int,
        rows_rejected: int,
        duration_ms: int,
        error_message: str | None = None,
    ) -> IngestionEvent:
        event = IngestionEvent(
            asset_id=asset_id,
            timeframe=timeframe,
            status=status,
            range_start=range_start,
            range_end=range_end,
            rows_processed=rows_processed,
            rows_inserted=rows_inserted,
            rows_rejected=rows_rejected,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        self._db.add(event)
        self._db.commit()
        self._db.refresh(event)
        return event

    def get_latest_ingestion_events(self, limit: int = 20) -> list[IngestionEvent]:
        stmt = select(IngestionEvent).order_by(IngestionEvent.created_at.desc()).limit(limit)
        return list(self._db.execute(stmt).scalars().all())