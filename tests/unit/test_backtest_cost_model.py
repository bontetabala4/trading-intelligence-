from types import SimpleNamespace

import pytest

from core.backtest.domain import BacktestCostModel


def test_mt5_bar_spread_points_require_explicit_point_conversion():
    model = BacktestCostModel(
        use_bar_spread=True,
        bar_spread_point_value=0.00001,
        price_basis="BID",
    )
    bar = SimpleNamespace(spread=10.0, high=1.1010, low=1.1000)
    assert model.spread_price_for_bar(bar) == pytest.approx(0.0001)


def test_fixed_spread_is_not_mistaken_for_raw_mt5_points():
    model = BacktestCostModel(spread_points=1.0, point_value=0.0001)
    bar = SimpleNamespace(spread=10.0, high=1.1010, low=1.1000)
    # 1 configured pip -> 0.0001 price units; bar.spread is intentionally ignored.
    assert model.spread_price_for_bar(bar) == pytest.approx(0.0001)


def test_bar_spread_mode_requires_explicit_converter():
    with pytest.raises(ValueError, match="bar_spread_point_value"):
        BacktestCostModel(use_bar_spread=True)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"spread_points": -1.0},
        {"slippage_points": -0.1},
        {"commission_per_trade_r": -0.01},
        {"point_value": 0.0},
        {"point_value": float("nan")},
        {"bar_spread_point_value": float("inf")},
        {"price_basis": "UNKNOWN"},
    ],
)
def test_invalid_cost_model_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        BacktestCostModel(**kwargs)


def test_bid_ask_quote_conversion_respects_price_basis():
    mid = BacktestCostModel(price_basis="MID")
    bid = BacktestCostModel(price_basis="BID")
    ask = BacktestCostModel(price_basis="ASK")
    assert mid.bid_ask_from_price(1.1000, 0.0002) == pytest.approx((1.0999, 1.1001))
    assert bid.bid_ask_from_price(1.1000, 0.0002) == pytest.approx((1.1000, 1.1002))
    assert ask.bid_ask_from_price(1.1000, 0.0002) == pytest.approx((1.0998, 1.1000))
