"""
Décision canonique V1 — une seule entrée vers ATIPPipeline.

Observation (broker OHLCV) → pipeline complet → FinalSignal.
Aucune logique BUY/SELL parallèle ici.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from brokers.base.interface import BrokerInterface, Timeframe
from configs.settings import Settings, get_settings
from core.market.selection import AssetClass
from core.pipeline import ATIPPipeline, MarketSnapshot, PipelineResult
from database.models import DecisionRecord
from database.repositories.decision_repository import DecisionRecordRepository


class DecisionServiceError(RuntimeError):
    """Impossible de produire une décision (broker, données, etc.)."""


def build_pipeline_snapshot(
    symbol: str,
    asset_class: AssetClass,
    timeframe: Timeframe,
    broker: BrokerInterface,
    lookback: int = 500,
) -> MarketSnapshot:
    if not broker.is_connected():
        raise DecisionServiceError(
            "Broker non connecté — impossible de construire un snapshot pipeline."
        )

    info = broker.get_symbol_info(symbol.upper())
    if not info.exists:
        raise DecisionServiceError(f"Symbole inconnu chez le broker : {symbol}")

    bars = broker.get_ohlcv(symbol.upper(), timeframe, count=lookback)
    if not bars:
        raise DecisionServiceError(
            f"Aucune bougie pour {symbol}/{timeframe.value}."
        )

    ordered = tuple(sorted(bars, key=lambda bar: bar.timestamp))
    timestamp = ordered[-1].timestamp

    return MarketSnapshot(
        symbol=symbol.upper(),
        asset_class=asset_class.value,
        timeframe=timeframe,
        timestamp=timestamp,
        bars=ordered,
    )


def run_decision(
    symbol: str,
    asset_class: AssetClass,
    timeframe: Timeframe,
    broker: BrokerInterface,
    pipeline: ATIPPipeline | None = None,
    lookback: int = 500,
) -> PipelineResult:
    snapshot = build_pipeline_snapshot(
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        broker=broker,
        lookback=lookback,
    )
    engine = pipeline or ATIPPipeline()
    return engine.process(snapshot)


def persist_decision(
    db: Session,
    result: PipelineResult,
    settings: Settings | None = None,
) -> DecisionRecord:
    """Enregistre le résultat pipeline en base (idempotent sur signal_id)."""
    repo = DecisionRecordRepository(db)
    return repo.save_pipeline_result(result, settings or get_settings())


def decision_record_to_dict(record: DecisionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "signal_id": record.signal_id,
        "symbol": record.symbol,
        "asset_class": record.asset_class,
        "timeframe": record.timeframe,
        "bar_timestamp": record.bar_timestamp.isoformat(),
        "direction": record.direction,
        "no_trade_reason": record.no_trade_reason,
        "strategy": record.strategy,
        "market_regime": record.market_regime,
        "opportunity_status": record.opportunity_status,
        "opportunity_score": record.opportunity_score,
        "risk_status": record.risk_status,
        "risk_score": record.risk_score,
        "data_quality_status": record.data_quality_status,
        "data_quality_score": record.data_quality_score,
        "entry_reference": record.entry_reference,
        "stop_reference": record.stop_reference,
        "target_reference": record.target_reference,
        "risk_reward": record.risk_reward,
        "broker_backend": record.broker_backend,
        "app_env": record.app_env,
        "engine_version": record.engine_version,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


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


def pipeline_result_to_dict(result: PipelineResult) -> dict[str, Any]:
    """Sérialisation stable pour l'API et l'historique futur."""
    sig = result.signal
    opportunity = result.opportunity_result
    regime = result.regime

    return {
        "decision": {
            "signal_id": sig.signal_id,
            "symbol": sig.symbol,
            "asset_class": sig.asset_class,
            "timeframe": sig.timeframe,
            "timestamp": sig.timestamp.isoformat(),
            "direction": sig.direction.value,
            "no_trade_reason": sig.no_trade_reason.value,
            "strategy": sig.strategy,
            "market_regime": sig.market_regime,
            "opportunity_status": sig.opportunity_status,
            "opportunity_score": sig.opportunity_score,
            "risk_status": sig.risk_status,
            "risk_score": sig.risk_score,
            "data_quality_status": sig.data_quality_status,
            "reasons": list(sig.reasons),
            "entry_reference": sig.entry_reference,
            "stop_reference": sig.stop_reference,
            "target_reference": sig.target_reference,
            "risk_reward": sig.risk_reward,
            "signal_version": sig.signal_version,
        },
        "data_quality_score": result.data_quality_score,
        "features": _to_jsonable(result.features),
        "regime": _to_jsonable(regime),
        "opportunity": _to_jsonable(opportunity),
        "strategy_signal": _to_jsonable(result.strategy_signal),
    }
