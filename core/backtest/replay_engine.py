"""
Historical Replay Engine — Delivers data strictly up to T (No-Lookahead).
"""
from typing import List, Tuple
from core.backtest.clock import SimulationClock
from core.features.domain.ohlcv_series import OHLCVSeries


class HistoricalReplayEngine:
    def __init__(self, bars: List[OHLCVSeries], clock: SimulationClock):
        self._bars = bars
        self._clock = clock
        self._cursor = 0

    def has_next(self) -> bool:
        return self._cursor < len(self._bars)

    def next_step(self) -> Tuple[OHLCVSeries, List[OHLCVSeries]]:
        """
        Advances to current bar T, sets SimulationClock to T, 
        and returns (current_bar, history_bars_<=_T).
        """
        if not self.has_next():
            raise IndexError("Replay engine reached end of dataset.")

        if hasattr(self._bars, "iloc"):
            current_bar = self._bars.iloc[self._cursor]
        else:
            current_bar = self._bars[self._cursor]

        self._clock.set_time(current_bar.timestamp)
        
        # Strictly slice history up to current cursor T
        history_slice = self._bars[: self._cursor + 1]
        self._cursor += 1

        return current_bar, history_slice
        