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