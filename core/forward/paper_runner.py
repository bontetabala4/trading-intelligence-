"""
Forward Paper Runner

Utilise EXACTEMENT le même ATIPPipeline que le BacktestRunner.

Différence uniquement sur la source des données :
- Backtest = historique
- Forward = nouvelles bougies

La logique de décision ne doit jamais être dupliquée.
"""

from core.pipeline import (
    ATIPPipeline,
    MarketSnapshot,
)

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
        asset_class: str,
        timeframe: Timeframe,
        bars: list[OHLCVBar],
    ):
        """
        Traite une observation Forward.

        Le dernier bar représente T.
        """

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