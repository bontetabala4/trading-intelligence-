import pytest
from pydantic import ValidationError

from brokers.base.interface import Timeframe
from core.market.selection import AssetClass, MarketSelection, Mode, TradingStyle


def test_valid_configuration_is_accepted():
    selection = MarketSelection(
        asset_class=AssetClass.METALS,
        symbol="xauusd",  # volontairement en minuscule
        trading_style=TradingStyle.DAY_TRADING,
        timeframe=Timeframe.M15,
        mode=Mode.ANALYSIS_ONLY,
    )
    assert selection.symbol == "XAUUSD"  # normalisé en majuscules
    assert selection.mode == Mode.ANALYSIS_ONLY


def test_default_mode_is_analysis_only():
    selection = MarketSelection(
        asset_class=AssetClass.FOREX,
        symbol="EURUSD",
        trading_style=TradingStyle.SWING_TRADING,
        timeframe=Timeframe.H4,
    )
    assert selection.mode == Mode.ANALYSIS_ONLY


def test_live_mode_is_rejected_at_this_stage():
    with pytest.raises(ValidationError):
        MarketSelection(
            asset_class=AssetClass.FOREX,
            symbol="EURUSD",
            trading_style=TradingStyle.DAY_TRADING,
            timeframe=Timeframe.M15,
            mode=Mode.LIVE,
        )


def test_empty_symbol_is_rejected():
    with pytest.raises(ValidationError):
        MarketSelection(
            asset_class=AssetClass.FOREX,
            symbol="   ",
            trading_style=TradingStyle.DAY_TRADING,
            timeframe=Timeframe.M15,
        )


def test_unknown_asset_class_is_rejected():
    with pytest.raises(ValidationError):
        MarketSelection(
            asset_class="not_a_real_class",
            symbol="EURUSD",
            trading_style=TradingStyle.DAY_TRADING,
            timeframe=Timeframe.M15,
        )


def test_style_matches_timeframe_hint():
    scalping = MarketSelection(
        asset_class=AssetClass.FOREX,
        symbol="EURUSD",
        trading_style=TradingStyle.SCALPING,
        timeframe=Timeframe.M1,
    )
    assert scalping.style_matches_timeframe() is True

    mismatched = MarketSelection(
        asset_class=AssetClass.FOREX,
        symbol="EURUSD",
        trading_style=TradingStyle.SCALPING,
        timeframe=Timeframe.D1,
    )
    assert mismatched.style_matches_timeframe() is False
