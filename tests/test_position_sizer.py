from core.risk.services.sizer import PositionSizer
from brokers.base.interface import SymbolInfo


def test_position_sizer_mt5_symbol_specs():
    sizer = PositionSizer(risk_per_trade_pct=0.01)

    symbol_info = SymbolInfo(
        symbol="XAUUSD",
        exists=True,
        tradable=True,
        digits=2,
        point=0.01,
        trade_tick_size=0.01,
        trade_tick_value=1.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        trade_contract_size=100.0,
    )

    lots = sizer.calculate_lot_size(
        balance=10_000.0,
        sl_distance=2.0,
        symbol_info=symbol_info,
    )

    # 100$ de risque / (2.0 / 0.01 × 1$) = 0.50 lot
    assert lots == 0.50

def test_position_sizer_fixed_risk_amount_10():
    sizer = PositionSizer(
        risk_mode="FIXED_AMOUNT",
        fixed_risk_amount=10.0,
    )

    lots = sizer.calculate_lot_size(
        balance=10_000.0,
        sl_distance=2.0,
        symbol_info=None,
    )

    # 10$ de risque / (200 pips × 10$/pip) = 0.005 lot
    # Sous le minimum de 0.01 lot => rejet.
    assert lots == 0.0


def test_position_sizer_fixed_risk_amount_100():
    sizer = PositionSizer(
        risk_mode="FIXED_AMOUNT",
        fixed_risk_amount=100.0,
    )

    lots = sizer.calculate_lot_size(
        balance=10_000.0,
        sl_distance=0.0015,
        symbol_info=None,
    )

    # 100$ / (15 pips × 10$/pip) = 0.666... => 0.66 lot
    assert lots == 0.66


def test_position_sizer_caps_to_highest_volume_step_below_broker_maximum():
    sizer = PositionSizer(risk_per_trade_pct=0.01)
    symbol_info = SymbolInfo(
        symbol="XAUUSD",
        exists=True,
        tradable=True,
        digits=2,
        point=0.01,
        trade_tick_size=0.01,
        trade_tick_value=1.0,
        volume_min=0.01,
        volume_max=0.025,
        volume_step=0.01,
        trade_contract_size=100.0,
    )

    lots = sizer.calculate_lot_size(
        balance=1_000_000.0,
        sl_distance=0.01,
        symbol_info=symbol_info,
    )

    assert lots == 0.02
    assert lots <= symbol_info.volume_max
    assert abs((lots / symbol_info.volume_step) - round(lots / symbol_info.volume_step)) < 1e-8


def test_position_sizer_rejects_incomplete_broker_volume_specs():
    sizer = PositionSizer(risk_per_trade_pct=0.01)
    incomplete = SymbolInfo(
        symbol="EURUSD",
        exists=True,
        tradable=True,
        digits=5,
        point=0.00001,
        trade_tick_size=0.00001,
        trade_tick_value=1.0,
        volume_min=None,
        volume_max=None,
        volume_step=None,
    )

    assert sizer.calculate_lot_size(
        balance=10_000.0,
        sl_distance=0.0015,
        symbol_info=incomplete,
    ) == 0.0


def test_position_sizer_rejects_non_finite_inputs_and_symbol_specs():
    sizer = PositionSizer(risk_per_trade_pct=0.01)
    complete = SymbolInfo(
        symbol="EURUSD",
        exists=True,
        tradable=True,
        digits=5,
        point=0.00001,
        trade_tick_size=float("nan"),
        trade_tick_value=1.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )

    assert sizer.calculate_lot_size(
        balance=float("nan"), sl_distance=0.0015
    ) == 0.0
    assert sizer.calculate_lot_size(
        balance=10_000.0, sl_distance=float("inf")
    ) == 0.0
    assert sizer.calculate_lot_size(
        balance=10_000.0, sl_distance=0.0015, symbol_info=complete
    ) == 0.0


def test_position_sizer_rejects_invalid_configuration():
    for kwargs in ({"lot_step": 0.0}, {"min_lot": 0.1, "max_lot": 0.01}, {"risk_per_trade_pct": float("nan")}):
        try:
            PositionSizer(**kwargs)
        except ValueError:
            continue
        raise AssertionError(f"PositionSizer should reject invalid configuration: {kwargs!r}")
