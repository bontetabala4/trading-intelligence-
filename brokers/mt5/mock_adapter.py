"""
MockMT5Adapter — double de test respectant BrokerInterface.

Utilisé quand BROKER_BACKEND=mock : tests unitaires, CI (Linux),
développement sur macOS/Linux sans terminal MT5 réel.

Génère des données OHLCV synthétiques déterministes (seedées) pour que
les tests soient reproductibles, plus quelques symboles connus pour
simuler un catalogue broker réaliste.
"""
import random
from datetime import datetime, timedelta, timezone

from brokers.base.interface import (
    AccountInfo,
    BrokerInterface,
    OHLCVBar,
    SymbolInfo,
    TerminalInfo,
    Timeframe,
)

_KNOWN_SYMBOLS = {
    "EURUSD": ("forex", 1.0850),
    "GBPUSD": ("forex", 1.2650),
    "USDJPY": ("forex", 149.50),
    "XAUUSD": ("metals", 2650.00),
    "XAGUSD": ("metals", 31.20),
    "NAS100": ("indices", 20500.0),
    "US30": ("indices", 42500.0),
    "SPX500": ("indices", 5800.0),
    "BTCUSD": ("crypto", 62000.0),
    "ETHUSD": ("crypto", 2600.0),
}

_TIMEFRAME_MINUTES = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1440,
    Timeframe.W1: 10080,
}


class MockMT5Adapter(BrokerInterface):
    """Double déterministe de MT5Adapter — aucune dépendance externe."""

    def __init__(self, seed: int = 42) -> None:
        self._connected = False
        self._rng = random.Random(seed)

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_terminal_info(self) -> TerminalInfo:
        return TerminalInfo(
            connected=self._connected, name="MockTerminal", build=0, trade_allowed=False
        )

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(
            login=0,
            server="mock-server",
            balance=10_000.0,
            equity=10_000.0,
            currency="USD",
            leverage=100,
            trade_allowed=False,
        )

    def list_symbols(self) -> list[str]:
        return list(_KNOWN_SYMBOLS.keys())

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        if symbol not in _KNOWN_SYMBOLS:
            return SymbolInfo(symbol=symbol, exists=False, tradable=False)
        asset_class, _ = _KNOWN_SYMBOLS[symbol]
        return SymbolInfo(
            symbol=symbol,
            exists=True,
            tradable=True,
            description=f"Mock {symbol} ({asset_class})",
            currency_base=symbol[:3],
            currency_quote=symbol[3:6] if len(symbol) >= 6 else "USD",
            digits=5,
        )

    def get_ohlcv(
        self, symbol: str, timeframe: Timeframe, count: int = 500
    ) -> list[OHLCVBar]:
        if symbol not in _KNOWN_SYMBOLS:
            return []

        _, base_price = _KNOWN_SYMBOLS[symbol]
        minutes = _TIMEFRAME_MINUTES[timeframe]
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

        bars: list[OHLCVBar] = []
        price = base_price
        for i in range(count, 0, -1):
            ts = now - timedelta(minutes=minutes * i)
            bars.append(self._synthesize_bar(ts, price))
            price = bars[-1].close

        return bars

    def get_ohlcv_range(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[OHLCVBar]:
        if symbol not in _KNOWN_SYMBOLS:
            return []
        if start >= end:
            return []

        _, base_price = _KNOWN_SYMBOLS[symbol]
        minutes = _TIMEFRAME_MINUTES[timeframe]
        step = timedelta(minutes=minutes)

        # Déterministe : la graine dérive du symbole pour que deux appels sur
        # la même plage produisent les mêmes bougies (idempotence testable).
        local_rng = random.Random(hash((symbol, timeframe.value)) & 0xFFFFFFFF)

        bars: list[OHLCVBar] = []
        price = base_price
        ts = start
        while ts <= end:
            # Week-end simulé fermé (samedi=5, dimanche=6) pour les classes
            # d'actifs qui ferment le week-end — le Mock reste simple mais
            # cohérent avec ce que le Calendar attend en "gap attendu".
            if ts.weekday() < 5 or _KNOWN_SYMBOLS[symbol][0] == "crypto":
                bars.append(self._synthesize_bar(ts, price, rng=local_rng))
                price = bars[-1].close
            ts += step

        return bars

    def _synthesize_bar(self, ts: datetime, price: float, rng: random.Random | None = None) -> OHLCVBar:
        rng = rng or self._rng
        drift = rng.uniform(-0.001, 0.001) * price
        open_ = price
        close = price + drift
        high = max(open_, close) + abs(drift) * rng.uniform(0, 1)
        low = min(open_, close) - abs(drift) * rng.uniform(0, 1)
        tick_vol = round(rng.uniform(50, 500), 2)
        return OHLCVBar(
            timestamp=ts,
            open=round(open_, 5),
            high=round(high, 5),
            low=round(low, 5),
            close=round(close, 5),
            volume=tick_vol,
            spread=round(rng.uniform(0.5, 2.5), 2),
            tick_volume=tick_vol,
            real_volume=None,  # Le Mock ne simule pas de volume réel — cohérent avec le Forex/CFD réel.
        )
