"""
HistoricalDataCollector — orchestration Collector → Validator → Normalizer
→ Repository, avec collecte incrémentale, batching, retry borné et suivi d'état.
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from brokers.base.interface import (
    BrokerConnectionError,
    BrokerInterface,
    Timeframe,
)
from core.data.normalizer import TimestampNormalizer
from core.data.validator import MarketDataValidationResult, MarketDataValidator
from core.market.selection import AssetClass
from database.repositories.asset_repository import AssetRepository
from database.repositories.market_data_repository import MarketDataRepository

logger = logging.getLogger("atip.data.collector")

_TIMEFRAME_SECONDS = {
    Timeframe.M1: 60,
    Timeframe.M5: 300,
    Timeframe.M15: 900,
    Timeframe.M30: 1800,
    Timeframe.H1: 3600,
    Timeframe.H4: 14400,
    Timeframe.D1: 86400,
    Timeframe.W1: 604800,
}

_DEFAULT_BATCH_SIZE = 5000


class CollectionStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass
class CollectionResult:
    status: CollectionStatus
    symbol: str
    timeframe: Timeframe
    range_start: datetime | None
    range_end: datetime | None
    rows_received: int = 0
    rows_inserted: int = 0
    rows_rejected: int = 0
    duration_ms: int = 0
    errors: list[str] = field(default_factory=list)
    validation: MarketDataValidationResult | None = None


class HistoricalDataCollector:
    def __init__(
        self,
        broker: BrokerInterface,
        asset_repo: AssetRepository,
        market_data_repo: MarketDataRepository,
        validator: MarketDataValidator | None = None,
        normalizer: TimestampNormalizer | None = None,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.05,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        self._broker = broker
        self._asset_repo = asset_repo
        self._market_data_repo = market_data_repo
        self._validator = validator or MarketDataValidator()
        self._normalizer = normalizer or TimestampNormalizer()
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._batch_size = batch_size

    def collect(
        self,
        symbol: str,
        asset_class: AssetClass,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        source: str = "mt5",
    ) -> CollectionResult:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start et end doivent être timezone-aware (UTC recommandé).")
        if start > end:
            raise ValueError("start doit être antérieur ou égal à end.")

        t0 = time.monotonic()
        errors: list[str] = []
        all_bars = []

        asset = self._asset_repo.get_or_create(symbol, asset_class.value, broker=source)

        for batch_start, batch_end in self._split_into_batches(start, end, timeframe):
            bars = self._fetch_with_retry(symbol, timeframe, batch_start, batch_end, errors)
            if bars:
                all_bars.extend(bars)

        normalized = self._normalizer.normalize_batch(all_bars)
        validation = self._validator.validate(normalized, timeframe, asset_class)
        clean_bars, rejected_count = self._filter_invalid(normalized)

        rows_inserted = 0
        if clean_bars:
            rows_inserted = self._market_data_repo.save_batch(
                asset.id, timeframe.value, clean_bars, source=source
            )

        duration_ms = int((time.monotonic() - t0) * 1000)

        if errors and not all_bars:
            status = CollectionStatus.FAILED
        elif errors:
            status = CollectionStatus.PARTIAL
        else:
            status = CollectionStatus.SUCCESS

        self._market_data_repo.record_ingestion_event(
            asset_id=asset.id,
            timeframe=timeframe.value,
            status=status.value,
            range_start=start,
            range_end=end,
            rows_processed=len(normalized),
            rows_inserted=rows_inserted,
            rows_rejected=rejected_count,
            duration_ms=duration_ms,
            error_message="; ".join(errors) if errors else None,
        )

        return CollectionResult(
            status=status,
            symbol=symbol,
            timeframe=timeframe,
            range_start=start,
            range_end=end,
            rows_received=len(normalized),
            rows_inserted=rows_inserted,
            rows_rejected=rejected_count,
            duration_ms=duration_ms,
            errors=errors,
            validation=validation,
        )

    def collect_incremental(
        self,
        symbol: str,
        asset_class: AssetClass,
        timeframe: Timeframe,
        default_lookback_days: int = 30,
        source: str = "mt5",
    ) -> CollectionResult:
        now = datetime.now(timezone.utc)
        asset = self._asset_repo.get_or_create(symbol, asset_class.value, broker=source)
        last_ts = self._market_data_repo.get_last_timestamp(asset.id, timeframe.value)

        if last_ts is None:
            start = now - timedelta(days=default_lookback_days)
        else:
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)

            step = timedelta(seconds=_TIMEFRAME_SECONDS[timeframe])
            start = last_ts + step

        if start >= now:
            return CollectionResult(
                status=CollectionStatus.SUCCESS,
                symbol=symbol,
                timeframe=timeframe,
                range_start=start,
                range_end=now,
                rows_received=0,
                rows_inserted=0,
            )

        return self.collect(symbol, asset_class, timeframe, start, now, source=source)

    # --- méthodes internes ---

    def _split_into_batches(
        self, start: datetime, end: datetime, timeframe: Timeframe
    ) -> list[tuple[datetime, datetime]]:
        span_seconds = _TIMEFRAME_SECONDS[timeframe] * self._batch_size
        step = timedelta(seconds=span_seconds)
        batches = []
        cursor = start
        while cursor < end:
            batch_end = min(cursor + step, end)
            batches.append((cursor, batch_end))
            cursor = batch_end
        return batches or [(start, end)]

    def _fetch_with_retry(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        errors: list[str],
    ) -> list | None:
        attempt = 0
        while attempt <= self._max_retries:
            try:
                return self._broker.get_ohlcv_range(symbol, timeframe, start, end)
            except BrokerConnectionError as exc:
                attempt += 1
                logger.warning(
                    "Échec collecte %s/%s [%s→%s], tentative %d/%d : %s",
                    symbol,
                    timeframe.value,
                    start,
                    end,
                    attempt,
                    self._max_retries,
                    exc,
                )
                if attempt > self._max_retries:
                    errors.append(str(exc))
                    return None
                time.sleep(self._retry_backoff_seconds * attempt)
            except Exception as exc:
                logger.error("Erreur inattendue pendant la collecte : %s", exc)
                errors.append(str(exc))
                return None
        return None

    @staticmethod
    def _filter_invalid(bars) -> tuple[list, int]:
        clean = []
        rejected = 0
        for bar in bars:
            if bar.high < bar.low or not (bar.low <= bar.open <= bar.high) or not (
                bar.low <= bar.close <= bar.high
            ):
                rejected += 1
                continue
            clean.append(bar)
        return clean, rejected