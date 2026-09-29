
from core.pipeline import ATIPPipeline
from core.market.snapshot import MarketSnapshot
from core.market.selection import AssetClass

from brokers.base.interface import (
    OHLCVBar,
    Timeframe,
)


class ForwardPaperRunner:

    def __init__(
        self,
        pipeline: ATIPPipeline,
    ) -> None:

        self.pipeline = pipeline

    def process_snapshot(
        self,
        symbol: str,
        asset_class: AssetClass,
        timeframe: Timeframe,
        bars: list[OHLCVBar],
    ):

        if not bars:
            raise ValueError(
                "ForwardPaperRunner nécessite au moins "
                "une bougie."
            )

        ordered_bars = sorted(
            bars,
            key=lambda bar: bar.timestamp,
        )

        current_bar = ordered_bars[-1]

        snapshot = MarketSnapshot(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe,
            timestamp=current_bar.timestamp,
            bars=tuple(ordered_bars),
        )

        return self.pipeline.process(
            snapshot
        )