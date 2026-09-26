"""
Forward Clock Module for Paper Trading / Forward Simulation.
Provides an explicit time abstraction (ForwardClock) that manages current_time and current_bar_index.
Prevents any usage of datetime.now() for market time evaluation.
"""

from datetime import datetime
from typing import Optional


class ForwardClock:
    def __init__(self, initial_time: Optional[datetime] = None):
        self._current_time: Optional[datetime] = initial_time
        self._current_bar_index: int = -1

    @property
    def current_time(self) -> Optional[datetime]:
        return self._current_time

    @property
    def current_bar_index(self) -> int:
        return self._current_bar_index

    def tick(self, timestamp: datetime, bar_index: int) -> None:
        """Advance the clock to the next bar's timestamp and index."""
        if self._current_time is not None and timestamp < self._current_time:
            raise ValueError(f"Clock cannot move backwards: {timestamp} < {self._current_time}")
        self._current_time = timestamp
        self._current_bar_index = bar_index

    def reset(self, initial_time: Optional[datetime] = None) -> None:
        self._current_time = initial_time
        self._current_bar_index = -1