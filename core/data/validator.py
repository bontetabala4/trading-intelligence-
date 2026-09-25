"""
MarketDataValidator — composant Étape 2 qui enrichit DataQualityEngine
avec la classification EXPECTED GAP / UNEXPECTED GAP (section 10), en
s'appuyant sur MarketCalendar. Ne remplace pas DataQualityEngine, le compose.
"""
from dataclasses import dataclass, field

from brokers.base.interface import OHLCVBar, Timeframe
from core.data.quality_engine import DataQualityEngine, DataQualityReport
from core.market.calendar import MarketCalendar
from core.market.selection import AssetClass

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


@dataclass
class GapInfo:
    start: object  # datetime
    end: object  # datetime
    expected: bool


@dataclass
class MarketDataValidationResult:
    quality: DataQualityReport
    expected_gaps: list[GapInfo] = field(default_factory=list)
    unexpected_gaps: list[GapInfo] = field(default_factory=list)


class MarketDataValidator:
    def __init__(
        self,
        quality_engine: DataQualityEngine | None = None,
        calendar: MarketCalendar | None = None,
    ) -> None:
        self._quality_engine = quality_engine or DataQualityEngine()
        self._calendar = calendar or MarketCalendar()

    def validate(
        self, bars: list[OHLCVBar], timeframe: Timeframe, asset_class: AssetClass
    ) -> MarketDataValidationResult:
        report = self._quality_engine.evaluate(bars, timeframe)

        expected_gaps: list[GapInfo] = []
        unexpected_gaps: list[GapInfo] = []

        if bars:
            sorted_bars = sorted(bars, key=lambda b: b.timestamp)
            expected_delta = _TIMEFRAME_SECONDS[timeframe]
            for prev, curr in zip(sorted_bars, sorted_bars[1:]):
                gap_duration = curr.timestamp - prev.timestamp
                if gap_duration.total_seconds() > expected_delta * 1.5:
                    closed = self._calendar.closed_duration(
                        asset_class, prev.timestamp, curr.timestamp
                    )
                    # Un trou est "attendu" si la quasi-totalité de sa durée
                    # coïncide avec une fermeture connue (tolérance 10% pour
                    # les heures de bordure vendredi soir/dimanche soir que
                    # le calendrier simplifié — jours calendaires — n'isole
                    # pas précisément).
                    is_expected = closed.total_seconds() >= gap_duration.total_seconds() * 0.9
                    gap = GapInfo(start=prev.timestamp, end=curr.timestamp, expected=is_expected)
                    (expected_gaps if is_expected else unexpected_gaps).append(gap)

        return MarketDataValidationResult(
            quality=report,
            expected_gaps=expected_gaps,
            unexpected_gaps=unexpected_gaps,
        )
