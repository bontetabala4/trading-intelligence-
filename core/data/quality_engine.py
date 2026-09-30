
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from core.market.selection import AssetClass

from brokers.base.interface import OHLCVBar, Timeframe

logger = logging.getLogger("atip.data.quality")

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

# Au-delà de N périodes sans nouvelle bougie, la donnée est considérée
# obsolète. Volontairement généreux pour ne pas confondre "marché fermé"
# (weekend, jour férié) avec un vrai problème — l'Étape 1 ne connaît pas
# encore le calendrier de marché par asset_class (voir Risques, Phase C).
_STALE_AFTER_PERIODS = 5


class DataQualityStatus(str, Enum):
    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"


@dataclass
class DataQualityReport:
    status: DataQualityStatus
    score: float  # 0.0 (pire) à 1.0 (parfait)
    issues: list[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Étape 2 (section 11) — statistiques de couverture, calculées quand des
    # bougies sont disponibles ; restent à leur valeur par défaut sinon.
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    duplicate_count: int = 0
    invalid_count: int = 0
    missing_candles: int = 0


class DataQualityEngine:
    """Applique une série de règles déterministes sur une liste d'OHLCVBar."""

    def evaluate(
    self,
    bars: list[OHLCVBar],
    timeframe: Timeframe,
    asset_class: AssetClass | None = None,
) -> DataQualityReport:
        if not bars:
            return DataQualityReport(
                status=DataQualityStatus.INVALID,
                score=0.0,
                issues=["Aucune donnée reçue."],
            )

        issues: list[str] = []

        issues += self._check_ohlc_validity(bars)
        issues += self._check_nulls_and_nans(bars)
        issues += self._check_duplicates(bars)
        issues += self._check_gaps(bars, timeframe, asset_class)
        issues += self._check_staleness(bars, timeframe)

        score = self._compute_score(issues, total_bars=len(bars))
        status = self._status_from_score(score, issues)

        sorted_bars = sorted(bars, key=lambda b: b.timestamp)
        report = DataQualityReport(
            status=status,
            score=score,
            issues=issues,
            first_timestamp=sorted_bars[0].timestamp,
            last_timestamp=sorted_bars[-1].timestamp,
            duplicate_count=sum(1 for i in issues if "dupliquée" in i),
            invalid_count=sum(1 for i in issues if "OHLC invalide" in i),
            missing_candles=self._count_missing_candles(sorted_bars, timeframe),
        )
        logger.info(
            "DataQuality: status=%s score=%.3f issues=%d", status, score, len(issues)
        )
        return report

    @staticmethod
    def _count_missing_candles(sorted_bars: list[OHLCVBar], timeframe: Timeframe) -> int:
        """Compte le nombre de bougies manquantes sur tous les trous détectés
        (indépendamment de savoir si un trou est "attendu" — voir MarketDataValidator
        pour la classification attendu/inattendu qui nécessite la classe d'actif)."""
        expected_delta = _TIMEFRAME_SECONDS[timeframe]
        missing = 0
        for prev, curr in zip(sorted_bars, sorted_bars[1:]):
            delta = (curr.timestamp - prev.timestamp).total_seconds()
            periods = round(delta / expected_delta) - 1
            if periods > 0:
                missing += periods
        return missing

    # --- Règles individuelles ---

    @staticmethod
    def _check_ohlc_validity(bars: list[OHLCVBar]) -> list[str]:
        issues = []
        for bar in bars:
            if bar.high < bar.low:
                issues.append(f"OHLC invalide à {bar.timestamp}: high < low.")
            if not (bar.low <= bar.open <= bar.high):
                issues.append(f"OHLC invalide à {bar.timestamp}: open hors [low, high].")
            if not (bar.low <= bar.close <= bar.high):
                issues.append(f"OHLC invalide à {bar.timestamp}: close hors [low, high].")
        return issues

    @staticmethod
    def _check_nulls_and_nans(bars: list[OHLCVBar]) -> list[str]:
        issues = []
        for bar in bars:
            values = [bar.open, bar.high, bar.low, bar.close, bar.volume]
            if any(v is None for v in values):
                issues.append(f"Valeur nulle détectée à {bar.timestamp}.")
            elif any(isinstance(v, float) and v != v for v in values):  # NaN check
                issues.append(f"NaN détecté à {bar.timestamp}.")
        return issues

    @staticmethod
    def _check_duplicates(bars: list[OHLCVBar]) -> list[str]:
        seen = set()
        issues = []
        for bar in bars:
            if bar.timestamp in seen:
                issues.append(f"Bougie dupliquée à {bar.timestamp}.")
            seen.add(bar.timestamp)
        return issues

    @staticmethod
    def _is_expected_forex_weekend_gap(start: datetime, end: datetime) -> bool:
        
        return start.weekday() == 4 and end.weekday() in {6, 0}

    @staticmethod
    def _check_gaps(
        bars: list[OHLCVBar],
        timeframe: Timeframe,
        asset_class: AssetClass | None = None,
    ) -> list[str]:
        expected_delta = _TIMEFRAME_SECONDS[timeframe]
        issues = []
        sorted_bars = sorted(bars, key=lambda b: b.timestamp)

        for prev, curr in zip(sorted_bars, sorted_bars[1:]):
            delta = (curr.timestamp - prev.timestamp).total_seconds()

            if delta <= expected_delta * 3:
                continue

            if asset_class == AssetClass.FOREX and DataQualityEngine._is_expected_forex_weekend_gap(prev.timestamp, curr.timestamp):
                continue

            issues.append(
                f"Trou de données entre {prev.timestamp} et {curr.timestamp} "
                f"({delta / 60:.0f} min, attendu ~{expected_delta / 60:.0f} min)."
            )

        return issues
    
    @staticmethod
    def _check_staleness(bars: list[OHLCVBar], timeframe: Timeframe) -> list[str]:
        expected_delta = _TIMEFRAME_SECONDS[timeframe]
        latest = max(bars, key=lambda b: b.timestamp)
        age_seconds = (datetime.now(timezone.utc) - latest.timestamp).total_seconds()
        if age_seconds > expected_delta * _STALE_AFTER_PERIODS:
            return [
                f"Dernière bougie ({latest.timestamp}) trop ancienne "
                f"({age_seconds / 60:.0f} min) — marché possiblement fermé ou données obsolètes."
            ]
        return []

    # --- Agrégation ---

    @staticmethod
    def _compute_score(issues: list[str], total_bars: int) -> float:
        if not issues:
            return 1.0
        # Pénalité proportionnelle au nombre de problèmes relatif à la taille
        # de la série, plafonnée pour rester dans [0, 1].
        penalty = min(1.0, len(issues) / max(total_bars, 1) + 0.05 * len(issues))
        return round(max(0.0, 1.0 - penalty), 3)

    @staticmethod
    def _status_from_score(score: float, issues: list[str]) -> DataQualityStatus:
        has_critical = any(
            "invalide" in i.lower() or "aucune donnée" in i.lower() for i in issues
        )
        if has_critical or score < 0.5:
            return DataQualityStatus.INVALID
        if issues or score < 0.9:
            return DataQualityStatus.WARNING
        return DataQualityStatus.VALID
