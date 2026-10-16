"""
Décision canonique V1 — une seule entrée vers ATIPPipeline.

Observation (broker OHLCV) → pipeline complet → FinalSignal.
Aucune logique BUY/SELL parallèle ici.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from brokers.base.interface import BrokerConnectionError, BrokerInterface, MarketQuote, SymbolInfo, Timeframe
from configs.settings import Settings, get_settings
from core.market.selection import AssetClass
from core.pipeline import ATIPPipeline, PipelineResult
from core.market.snapshot import MarketSnapshot
from core.risk.domain.models import AccountState
from database.models import DecisionRecord
from database.repositories.decision_repository import DecisionRecordRepository
from pydantic import BaseModel

class DecisionServiceError(RuntimeError):
    """Impossible de produire une décision (broker, données, etc.)."""


MAX_CURRENT_QUOTE_AGE_SECONDS = 60.0
MAX_FUTURE_QUOTE_SECONDS = 5.0


def _usable_current_quote(
    quote: MarketQuote | None,
    *,
    now: datetime | None = None,
) -> tuple[float, float] | None:
    """Return (bid, ask) only for a valid, timezone-aware, recent quote."""
    if quote is None:
        return None
    instant = now or datetime.now(timezone.utc)
    try:
        timestamp = quote.timestamp
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return None
        bid = float(quote.bid)
        ask = float(quote.ask)
        age_seconds = (instant - timestamp.astimezone(timezone.utc)).total_seconds()
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(bid) or not math.isfinite(ask):
        return None
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    if age_seconds > MAX_CURRENT_QUOTE_AGE_SECONDS or age_seconds < -MAX_FUTURE_QUOTE_SECONDS:
        return None
    return bid, ask


def _build_pipeline_inputs(
    symbol: str,
    asset_class: AssetClass,
    timeframe: Timeframe,
    broker: BrokerInterface,
    lookback: int = 500,
) -> tuple[MarketSnapshot, SymbolInfo]:
    if not broker.is_connected():
        raise DecisionServiceError(
            "Broker non connecté — impossible de construire un snapshot pipeline."
        )

    info = broker.get_symbol_info(symbol.upper())
    if not info.exists:
        raise DecisionServiceError(f"Symbole inconnu chez le broker : {symbol}")

    bars = broker.get_closed_ohlcv(symbol.upper(), timeframe, count=lookback)
    if not bars:
        raise DecisionServiceError(
            f"Aucune bougie pour {symbol}/{timeframe.value}."
        )

    ordered = tuple(sorted(bars, key=lambda bar: bar.timestamp))
    snapshot = MarketSnapshot(
        symbol=symbol.upper(),
        asset_class=asset_class,
        timeframe=timeframe,
        timestamp=ordered[-1].timestamp,
        bars=ordered,
    )
    return snapshot, info


def build_pipeline_snapshot(
    symbol: str,
    asset_class: AssetClass,
    timeframe: Timeframe,
    broker: BrokerInterface,
    lookback: int = 500,
) -> MarketSnapshot:
    snapshot, _ = _build_pipeline_inputs(
        symbol, asset_class, timeframe, broker, lookback
    )
    return snapshot


def run_decision(
    symbol: str,
    asset_class: AssetClass,
    timeframe: Timeframe,
    broker: BrokerInterface,
    pipeline: ATIPPipeline | None = None,
    lookback: int = 500,
) -> PipelineResult:
    snapshot, symbol_info = _build_pipeline_inputs(
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        broker=broker,
        lookback=lookback,
    )

    # A decision may still explain the market when risk information is missing,
    # but it must become NO_TRADE rather than inventing capital/positions/PnL.
    account_state = None
    try:
        broker_account = broker.get_account_info()
    except BrokerConnectionError:
        broker_account = None

    if broker_account is not None and all(
        value is not None
        for value in (
            broker_account.free_margin,
            broker_account.daily_pnl,
            broker_account.open_positions_count,
        )
    ):
        try:
            account_state = AccountState(
                balance=float(broker_account.balance),
                equity=float(broker_account.equity),
                free_margin=float(broker_account.free_margin),
                daily_pnl=float(broker_account.daily_pnl),
                open_positions_count=int(broker_account.open_positions_count),
            )
        except (TypeError, ValueError):
            account_state = None

    # A historical candle spread is not a live quote. Use only a recent broker tick;
    # missing/invalid/stale quotes are passed as missing and force NO_TRADE in strict mode.
    try:
        broker_quote = broker.get_current_quote(symbol.upper())
    except BrokerConnectionError:
        broker_quote = None
    usable_quote = _usable_current_quote(broker_quote)

    current_bid = None
    current_ask = None
    current_spread_price = None
    current_spread_pips = None
    if usable_quote is not None:
        current_bid, current_ask = usable_quote
        current_spread_price = current_ask - current_bid
        if asset_class.value.lower() == "forex" and symbol_info.point is not None:
            point = float(symbol_info.point)
            if point > 0 and symbol_info.digits is not None:
                pip_multiplier = 10 if symbol_info.digits in (3, 5) else 1
                pip_size = point * pip_multiplier
                if pip_size > 0:
                    current_spread_pips = current_spread_price / pip_size

    engine = pipeline or ATIPPipeline()
    return engine.process(
        snapshot,
        symbol_info=symbol_info,
        account=account_state,
        current_spread_pips=current_spread_pips,
        current_spread_price=current_spread_price,
        current_bid=current_bid,
        current_ask=current_ask,
        require_explicit_risk_inputs=True,
    )

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
    if isinstance(value, BaseModel):
        return _to_jsonable(value.model_dump(mode="python"))
    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump(mode="python"))
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
