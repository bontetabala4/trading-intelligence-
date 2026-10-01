from datetime import datetime, timedelta, timezone

import pytest

from brokers.base.interface import OHLCVBar
from core.market.structure import (
    MarketStructureEngine,
    MarketStructureState,
    SwingType,
)


def make_bars(
    highs: list[float],
    lows: list[float],
) -> list[OHLCVBar]:
    assert len(highs) == len(lows)

    start = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    return [
        OHLCVBar(
            timestamp=start + timedelta(
                minutes=15 * index
            ),
            open=(high + low) / 2,
            high=high,
            low=low,
            close=(high + low) / 2,
            volume=1000,
        )
        for index, (high, low)
        in enumerate(zip(highs, lows))
    ]


def test_insufficient_bars_are_uncertain():
    result = MarketStructureEngine().analyze(
        make_bars(
            [1, 2, 1, 2],
            [0, 1, 0, 1],
        )
    )

    assert result.state == MarketStructureState.UNCERTAIN
    assert result.protected_level is None


def test_bullish_structure_and_protected_low():
    highs = [
        1,
        2,
        5,
        4,
        3,
        2,
        6,
        5,
        4,
        3,
        7,
        6,
        5,
        4,
        8,
    ]

    lows = [
        0,
        1,
        2,
        1,
        0,
        1,
        3,
        2,
        1,
        2,
        4,
        3,
        2,
        3,
        5,
    ]

    result = MarketStructureEngine().analyze(
        make_bars(
            highs,
            lows,
        )
    )

    assert result.state == MarketStructureState.BULLISH

    assert len(result.swing_highs) >= 2
    assert len(result.swing_lows) >= 2

    assert result.swing_highs[-1].price == 7
    assert result.swing_lows[-1].price == 2

    assert result.protected_level == 2

    assert (
        result.protected_level_type
        == SwingType.LOW
    )


def test_bearish_structure_and_protected_high():
    highs = [
        8,
        7,
        4,
        5,
        6,
        7,
        3,
        4,
        5,
        6,
        2,
        3,
        4,
        5,
        1,
    ]

    lows = [
        9,
        8,
        3,
        4,
        5,
        6,
        2,
        3,
        4,
        5,
        1,
        2,
        3,
        4,
        0,
    ]

    result = MarketStructureEngine().analyze(
        make_bars(
            highs,
            lows,
        )
    )

    assert result.state == MarketStructureState.BEARISH

    assert len(result.swing_highs) >= 2
    assert len(result.swing_lows) >= 2

    assert result.swing_highs[-1].price == 6
    assert result.swing_lows[-1].price == 1

    assert result.protected_level == 6

    assert (
        result.protected_level_type
        == SwingType.HIGH
    )


def test_mixed_structure_is_range():
    highs = [
        1, 2, 5, 4, 3, 2, 6, 5, 4,
        3, 2, 5, 4, 3, 2, 4, 3,
    ]

    lows = [
        0, 1, 2, 1, 0, 1, 3, 2, 1,
        0, 1, 2, 1, 0, 1, 2, 1,
    ]

    result = MarketStructureEngine().analyze(
        make_bars(
            highs,
            lows,
        )
    )

    assert result.state == MarketStructureState.RANGE

    assert len(result.swing_highs) >= 2
    assert len(result.swing_lows) >= 2

    assert result.protected_level is None
    assert result.protected_level_type is None

def test_swing_is_only_confirmed_after_right_bars():
    highs = [
        1,
        2,
        5,
        4,
        3,
    ]

    lows = [
        0,
        1,
        2,
        1,
        0,
    ]

    bars = make_bars(
        highs,
        lows,
    )

    result = MarketStructureEngine(
        left_bars=1,
        right_bars=1,
    ).analyze(bars)

    assert len(result.swing_highs) == 1

    swing = result.swing_highs[0]

    assert swing.timestamp < swing.confirmed_at

    assert (
        swing.timestamp
        == bars[2].timestamp
    )

    assert (
        swing.confirmed_at
        == bars[3].timestamp
    )


def test_new_bar_confirms_previous_swing():
    base_highs = [
        1,
        2,
        5,
    ]

    base_lows = [
        0,
        1,
        2,
    ]

    before = make_bars(
        base_highs,
        base_lows,
    )

    engine = MarketStructureEngine(
        left_bars=1,
        right_bars=1,
    )

    assert not engine.analyze(
        before
    ).swing_highs

    after = make_bars(
        base_highs + [4],
        base_lows + [1],
    )

    result = engine.analyze(after)

    assert len(result.swing_highs) == 1

    assert (
        result.swing_highs[0].timestamp
        == before[2].timestamp
    )

    assert (
        result.swing_highs[0].confirmed_at
        == after[3].timestamp
    )


def test_unsorted_bars_are_rejected():
    bars = make_bars(
        [2, 3, 2, 5, 4],
        [1, 2, 1, 2, 1],
    )

    bars[2], bars[3] = (
        bars[3],
        bars[2],
    )

    with pytest.raises(
        ValueError,
        match="chronologiquement",
    ):
        MarketStructureEngine().analyze(bars)


def test_equal_high_does_not_create_swing_high():
    highs = [
        1,
        3,
        3,
        3,
        1,
        4,
        2,
    ]

    lows = [
        0,
        1,
        0,
        1,
        0,
        2,
        1,
    ]

    result = MarketStructureEngine().analyze(
        make_bars(
            highs,
            lows,
        )
    )

    assert all(
        point.price != 3
        for point in result.swing_highs
    )