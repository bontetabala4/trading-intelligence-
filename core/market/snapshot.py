"""MarketSnapshot — DTO canonique du marché pour tout le pipeline ATIP."""

from dataclasses import dataclass
from datetime import datetime

from brokers.base.interface import OHLCVBar, Timeframe
from core.market.selection import AssetClass


@dataclass(frozen=True)
class MarketSnapshot:
    """
    Snapshot immuable utilisé par tous les modes d'exécution.

    Les bars doivent être :
    - triées chronologiquement ;
    - timezone-aware ;
    - toutes <= timestamp ;
    - la dernière bar doit correspondre exactement à timestamp.

    Cette contrainte est fondamentale pour empêcher le look-ahead.
    """

    symbol: str
    asset_class: AssetClass
    timeframe: Timeframe
    timestamp: datetime
    bars: tuple[OHLCVBar, ...]

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError(
                "MarketSnapshot.timestamp doit être timezone-aware."
            )

        object.__setattr__(self, "bars", tuple(self.bars))

        if not self.bars:
            raise ValueError(
                "MarketSnapshot doit contenir au moins une bougie."
            )

        ordered = tuple(
            sorted(
                self.bars,
                key=lambda bar: bar.timestamp,
            )
        )

        if ordered != self.bars:
            raise ValueError(
                "Les bars du MarketSnapshot doivent être triées "
                "chronologiquement."
            )

        if any(bar.timestamp > self.timestamp for bar in self.bars):
            raise ValueError(
                "Look-ahead détecté : une ou plusieurs bougies "
                "sont postérieures au timestamp du snapshot."
            )

        if self.bars[-1].timestamp != self.timestamp:
            raise ValueError(
                "La dernière bougie doit correspondre exactement "
                "au timestamp du snapshot."
            )