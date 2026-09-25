"""
TimestampNormalizer — garantit qu'aucune donnée n'entre dans le pipeline
sans un timestamp UTC timezone-aware explicite.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from brokers.base.interface import OHLCVBar


class NormalizationError(ValueError):
    """Levée quand un timestamp ne peut pas être normalisé en UTC de façon fiable."""


class TimestampNormalizer:
    def __init__(self, source_timezone: str = "UTC") -> None:
        self._source_tz = ZoneInfo(source_timezone)

    def normalize_bar(self, bar: OHLCVBar) -> OHLCVBar:
        normalized_ts = self._to_utc(bar.timestamp)
        if normalized_ts == bar.timestamp:
            return bar

        # Support universel Pydantic / Dataclass
        if hasattr(bar, "model_copy"):
            return bar.model_copy(update={"timestamp": normalized_ts})

        return OHLCVBar(
            timestamp=normalized_ts,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            spread=getattr(bar, "spread", None),
            tick_volume=getattr(bar, "tick_volume", None),
            real_volume=getattr(bar, "real_volume", None),
        )

    def normalize_batch(self, bars: list[OHLCVBar]) -> list[OHLCVBar]:
        return [self.normalize_bar(b) for b in bars]

    def _to_utc(self, ts: datetime) -> datetime:
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=self._source_tz)
        return ts.astimezone(timezone.utc)