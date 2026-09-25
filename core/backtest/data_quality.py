"""
Data Quality Analysis Models and Report Generator for ATIP Step 10.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass(frozen=True)
class DatasetMetadata:
    dataset_id: str
    source: str
    symbol: str
    asset_class: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    timezone: str
    total_bars: int
    data_format: str
    is_synthetic: bool = False


@dataclass
class QualityMetrics:
    total_bars: int = 0
    valid_bars: int = 0
    invalid_bars: int = 0
    duplicates: int = 0
    unexpected_gaps: int = 0
    expected_session_gaps: int = 0
    ohlc_violations: int = 0
    missing_volume: int = 0
    quality_status: str = "INVALID"  # VALID, WARNING, INVALID
    issues: List[str] = field(default_factory=list)


class DataQualityReport:
    """Generates standardized data quality reports before running historical backtests."""

    def __init__(self, metadata: DatasetMetadata, metrics: QualityMetrics):
        self.metadata = metadata
        self.metrics = metrics

    def generate_report_string(self) -> str:
        lines = [
            "==================================================",
            "           DATASET QUALITY REPORT                 ",
            "==================================================",
            f"Dataset ID           : {self.metadata.dataset_id}",
            f"Source               : {self.metadata.source}",
            f"Symbol / Asset Class : {self.metadata.symbol} ({self.metadata.asset_class})",
            f"Timeframe            : {self.metadata.timeframe}",
            f"Period               : {self.metadata.start_date.strftime('%Y-%m-%d')} -> {self.metadata.end_date.strftime('%Y-%m-%d')}",
            f"Timezone             : {self.metadata.timezone}",
            f"Is Synthetic Data    : {self.metadata.is_synthetic}",
            "--------------------------------------------------",
            f"Total Bars           : {self.metrics.total_bars}",
            f"Valid Bars           : {self.metrics.valid_bars}",
            f"Invalid Bars         : {self.metrics.invalid_bars}",
            f"Duplicates           : {self.metrics.duplicates}",
            f"OHLC Violations      : {self.metrics.ohlc_violations}",
            f"Missing Volume       : {self.metrics.missing_volume}",
            f"Expected Gaps        : {self.metrics.expected_session_gaps}",
            f"Unexpected Gaps      : {self.metrics.unexpected_gaps}",
            "--------------------------------------------------",
            f"QUALITY STATUS       : {self.metrics.quality_status}",
            "==================================================",
        ]
        if self.metrics.issues:
            lines.append("Detected Issues:")
            for issue in self.metrics.issues:
                lines.append(f" - {issue}")
            lines.append("==================================================")
        return "\n".join(lines)