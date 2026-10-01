
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from brokers.base.interface import OHLCVBar


class MarketStructureState(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGE = "RANGE"
    UNCERTAIN = "UNCERTAIN"


class SwingType(str, Enum):
    HIGH = "SWING_HIGH"
    LOW = "SWING_LOW"


@dataclass(frozen=True)
class SwingPoint:
    type: SwingType
    timestamp: object
    price: float
    index: int
    confirmed_at: object


@dataclass(frozen=True)
class MarketStructure:
    state: MarketStructureState
    swing_highs: tuple[SwingPoint, ...]
    swing_lows: tuple[SwingPoint, ...]
    protected_level: float | None
    protected_level_type: SwingType | None

    @property
    def last_swing_high(self) -> SwingPoint | None:
        return self.swing_highs[-1] if self.swing_highs else None

    @property
    def last_swing_low(self) -> SwingPoint | None:
        return self.swing_lows[-1] if self.swing_lows else None


class MarketStructureEngine:
    """Detect confirmed market structure from closed OHLCV bars."""

    def __init__(
        self,
        left_bars: int = 2,
        right_bars: int = 2,
    ) -> None:
        if left_bars <= 0 or right_bars <= 0:
            raise ValueError(
                "left_bars et right_bars doivent être > 0."
            )

        self._left_bars = left_bars
        self._right_bars = right_bars

    def analyze(
        self,
        bars: list[OHLCVBar] | tuple[OHLCVBar, ...],
    ) -> MarketStructure:
        ordered = tuple(bars)

        minimum_bars = (
            self._left_bars
            + self._right_bars
            + 1
        )

        if len(ordered) < minimum_bars:
            return MarketStructure(
                state=MarketStructureState.UNCERTAIN,
                swing_highs=(),
                swing_lows=(),
                protected_level=None,
                protected_level_type=None,
            )

        for previous, current in zip(
            ordered,
            ordered[1:],
        ):
            if current.timestamp <= previous.timestamp:
                raise ValueError(
                    "Les bars doivent être triées chronologiquement."
                )

        swing_highs: list[SwingPoint] = []
        swing_lows: list[SwingPoint] = []

        first_pivot = self._left_bars
        last_pivot = (
            len(ordered)
            - self._right_bars
            - 1
        )

        for index in range(
            first_pivot,
            last_pivot + 1,
        ):
            candidate = ordered[index]

            left_bars = ordered[
                index - self._left_bars:index
            ]

            right_bars = ordered[
                index + 1:
                index + self._right_bars + 1
            ]

            is_swing_high = all(
                candidate.high > bar.high
                for bar in (
                    *left_bars,
                    *right_bars,
                )
            )

            is_swing_low = all(
                candidate.low < bar.low
                for bar in (
                    *left_bars,
                    *right_bars,
                )
            )

            confirmed_at = ordered[
                index + self._right_bars
            ].timestamp

            if is_swing_high:
                swing_highs.append(
                    SwingPoint(
                        type=SwingType.HIGH,
                        timestamp=candidate.timestamp,
                        price=candidate.high,
                        index=index,
                        confirmed_at=confirmed_at,
                    )
                )

            if is_swing_low:
                swing_lows.append(
                    SwingPoint(
                        type=SwingType.LOW,
                        timestamp=candidate.timestamp,
                        price=candidate.low,
                        index=index,
                        confirmed_at=confirmed_at,
                    )
                )

        state = self._classify(
            swing_highs,
            swing_lows,
        )

        protected_level, protected_type = (
            self._protected_level(
                state,
                swing_highs,
                swing_lows,
            )
        )

        return MarketStructure(
            state=state,
            swing_highs=tuple(swing_highs),
            swing_lows=tuple(swing_lows),
            protected_level=protected_level,
            protected_level_type=protected_type,
        )

    @staticmethod
    def _classify(
        highs: list[SwingPoint],
        lows: list[SwingPoint],
    ) -> MarketStructureState:
        if len(highs) < 2 or len(lows) < 2:
            return MarketStructureState.UNCERTAIN

        higher_high = (
            highs[-1].price
            > highs[-2].price
        )

        higher_low = (
            lows[-1].price
            > lows[-2].price
        )

        lower_high = (
            highs[-1].price
            < highs[-2].price
        )

        lower_low = (
            lows[-1].price
            < lows[-2].price
        )

        if higher_high and higher_low:
            return MarketStructureState.BULLISH

        if lower_high and lower_low:
            return MarketStructureState.BEARISH

        return MarketStructureState.RANGE

    @staticmethod
    def _protected_level(
        state: MarketStructureState,
        highs: list[SwingPoint],
        lows: list[SwingPoint],
    ) -> tuple[float | None, SwingType | None]:

        if (
            state == MarketStructureState.BULLISH
            and lows
        ):
            return (
                lows[-1].price,
                SwingType.LOW,
            )

        if (
            state == MarketStructureState.BEARISH
            and highs
        ):
            return (
                highs[-1].price,
                SwingType.HIGH,
            )

        return None, None