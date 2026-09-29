"""Persistance des décisions ATIP (mémoire système V1)."""
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from configs.settings import Settings
from core.pipeline import PipelineResult
from database.models import DecisionRecord


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _to_jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


class DecisionRecordRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    @staticmethod
    def _config_snapshot(settings: Settings) -> dict:
        return {
            "app_env": settings.app_env.value,
            "broker_backend": settings.broker_backend.value,
            "trading_execution_enabled": settings.trading_execution_enabled,
            "data_collection_api_enabled": settings.data_collection_api_enabled,
        }

    def save_pipeline_result(
        self,
        result: PipelineResult,
        settings: Settings,
    ) -> DecisionRecord:
        sig = result.signal
        record = DecisionRecord(
            signal_id=sig.signal_id,
            symbol=sig.symbol,
            asset_class=sig.asset_class,
            timeframe=sig.timeframe,
            bar_timestamp=sig.timestamp,
            direction=sig.direction.value,
            no_trade_reason=sig.no_trade_reason.value,
            strategy=sig.strategy,
            market_regime=sig.market_regime,
            opportunity_status=sig.opportunity_status,
            opportunity_score=sig.opportunity_score,
            risk_status=sig.risk_status,
            risk_score=sig.risk_score,
            data_quality_status=sig.data_quality_status,
            data_quality_score=result.data_quality_score,
            entry_reference=sig.entry_reference,
            stop_reference=sig.stop_reference,
            target_reference=sig.target_reference,
            risk_reward=sig.risk_reward,
            reasons_json=json.dumps(list(sig.reasons)),
            features_json=json.dumps(_to_jsonable(result.features)),
            regime_json=json.dumps(_to_jsonable(result.regime))
            if result.regime is not None
            else None,
            opportunity_json=json.dumps(_to_jsonable(result.opportunity_result))
            if result.opportunity_result is not None
            else None,
            evidence_json=json.dumps(_to_jsonable(sig.evidence)),
            broker_backend=settings.broker_backend.value,
            app_env=settings.app_env.value,
            engine_version=sig.signal_version,
            config_json=json.dumps(self._config_snapshot(settings)),
        )
        self._db.add(record)
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            existing = self.get_by_signal_id(sig.signal_id)
            if existing is None:
                raise
            return existing
        self._db.refresh(record)
        return record

    def get_by_signal_id(self, signal_id: str) -> DecisionRecord | None:
        stmt = select(DecisionRecord).where(DecisionRecord.signal_id == signal_id)
        return self._db.scalars(stmt).first()

    def list_for_symbol(
        self,
        symbol: str,
        timeframe: str | None = None,
        limit: int = 50,
    ) -> list[DecisionRecord]:
        stmt = (
            select(DecisionRecord)
            .where(DecisionRecord.symbol == symbol.upper())
            .order_by(DecisionRecord.bar_timestamp.desc())
            .limit(limit)
        )
        if timeframe is not None:
            stmt = stmt.where(DecisionRecord.timeframe == timeframe)
        return list(self._db.scalars(stmt).all())
