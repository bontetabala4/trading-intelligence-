"""
MT5Adapter — implémentation réelle de BrokerInterface via le package
`MetaTrader5` (Windows uniquement, nécessite un terminal MT5 installé
et connecté à un compte).

Ce module est le SEUL endroit du projet qui importe le package `MetaTrader5`.
Tout le reste du système passe exclusivement par BrokerInterface.

READ ONLY à l'Étape 1 : execute_order() hérite du stub désactivé de la
classe de base et n'est pas surchargé ici.
"""
import logging
from datetime import datetime, timezone

from brokers.base.interface import (
    AccountInfo,
    BrokerConnectionError,
    BrokerInterface,
    OHLCVBar,
    SymbolInfo,
    TerminalInfo,
    Timeframe,
)

logger = logging.getLogger("atip.brokers.mt5")

_TIMEFRAME_MAP_BUILT = False
_TF_MAP: dict[Timeframe, int] = {}


def _build_timeframe_map() -> None:
    """Construit la table de correspondance Timeframe -> constante MT5 à l'import,
    seulement si le package MetaTrader5 est disponible (évite un crash sur
    machines non-Windows qui n'importeront jamais réellement cet adaptateur)."""
    global _TIMEFRAME_MAP_BUILT
    if _TIMEFRAME_MAP_BUILT:
        return
    import MetaTrader5 as mt5  # import local : ne casse rien si absent tant qu'on n'instancie pas MT5Adapter

    _TF_MAP.update(
        {
            Timeframe.M1: mt5.TIMEFRAME_M1,
            Timeframe.M5: mt5.TIMEFRAME_M5,
            Timeframe.M15: mt5.TIMEFRAME_M15,
            Timeframe.M30: mt5.TIMEFRAME_M30,
            Timeframe.H1: mt5.TIMEFRAME_H1,
            Timeframe.H4: mt5.TIMEFRAME_H4,
            Timeframe.D1: mt5.TIMEFRAME_D1,
            Timeframe.W1: mt5.TIMEFRAME_W1,
        }
    )
    _TIMEFRAME_MAP_BUILT = True


class MT5Adapter(BrokerInterface):
    """Adaptateur natif MT5. Nécessite Windows + terminal MT5 installé."""

    def __init__(
        self,
        path: str | None,
        login: int | None,
        password: str | None,
        server: str | None,
    ) -> None:
        self._path = path
        self._login = login
        self._password = password
        self._server = server
        self._connected = False

    def connect(self) -> None:
        import MetaTrader5 as mt5

        _build_timeframe_map()

        kwargs = {}
        if self._path:
            kwargs["path"] = self._path
        if self._login:
            kwargs["login"] = self._login
        if self._password:
            kwargs["password"] = self._password
        if self._server:
            kwargs["server"] = self._server

        ok = mt5.initialize(**kwargs)
        if not ok:
            error = mt5.last_error()
            # Ne jamais logger self._password — on log uniquement le code d'erreur MT5.
            logger.error("Échec connexion MT5 (code=%s)", error)
            raise BrokerConnectionError(f"MT5 initialize() a échoué : code {error}")

        self._connected = True
        logger.info("Connexion MT5 établie (server masqué dans les logs).")

    def disconnect(self) -> None:
        import MetaTrader5 as mt5

        mt5.shutdown()
        self._connected = False
        logger.info("Connexion MT5 fermée.")

    def is_connected(self) -> bool:
        import MetaTrader5 as mt5

        if not self._connected:
            return False
        # Health check actif : terminal_info() renvoie None si la connexion est morte.
        info = mt5.terminal_info()
        return info is not None and info.connected

    def get_terminal_info(self) -> TerminalInfo:
        import MetaTrader5 as mt5

        info = mt5.terminal_info()
        if info is None:
            return TerminalInfo(connected=False)
        return TerminalInfo(
            connected=info.connected,
            name=info.name,
            build=info.build,
            trade_allowed=info.trade_allowed,
        )

    def get_account_info(self) -> AccountInfo:
        import MetaTrader5 as mt5

        info = mt5.account_info()
        if info is None:
            raise BrokerConnectionError("Impossible de récupérer les infos du compte MT5.")
        return AccountInfo(
            login=info.login,
            server=info.server,
            balance=info.balance,
            equity=info.equity,
            currency=info.currency,
            leverage=info.leverage,
            trade_allowed=info.trade_allowed,
        )

    def list_symbols(self) -> list[str]:
        import MetaTrader5 as mt5

        symbols = mt5.symbols_get()
        if symbols is None:
            return []
        return [s.name for s in symbols]

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        import MetaTrader5 as mt5

        info = mt5.symbol_info(symbol)
        if info is None:
            return SymbolInfo(symbol=symbol, exists=False, tradable=False)
        return SymbolInfo(
            symbol=symbol,
            exists=True,
            tradable=info.visible and info.trade_mode != mt5.SYMBOL_TRADE_MODE_DISABLED,
            description=info.description,
            currency_base=info.currency_base,
            currency_quote=info.currency_profit,
            digits=info.digits,
        )

    def get_ohlcv(
        self, symbol: str, timeframe: Timeframe, count: int = 500
    ) -> list[OHLCVBar]:
        import MetaTrader5 as mt5

        _build_timeframe_map()
        mt5_tf = _TF_MAP[timeframe]

        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
        if rates is None:
            raise BrokerConnectionError(
                f"copy_rates_from_pos a échoué pour {symbol}/{timeframe.value}"
            )
        return [self._bar_from_rate(r) for r in rates]

    def get_ohlcv_range(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[OHLCVBar]:
        import MetaTrader5 as mt5

        _build_timeframe_map()
        mt5_tf = _TF_MAP[timeframe]

        rates = mt5.copy_rates_range(symbol, mt5_tf, start, end)
        if rates is None:
            # copy_rates_range renvoie None sur erreur réelle, mais un tableau
            # vide (pas None) quand la plage ne contient simplement aucune
            # donnée (ex: marché fermé) — on ne lève donc que sur None.
            error = mt5.last_error()
            raise BrokerConnectionError(
                f"copy_rates_range a échoué pour {symbol}/{timeframe.value} : {error}"
            )
        return [self._bar_from_rate(r) for r in rates]

    @staticmethod
    def _bar_from_rate(r) -> OHLCVBar:
        tick_volume = float(r["tick_volume"]) if "tick_volume" in r.dtype.names else None
        real_volume = (
            float(r["real_volume"])
            if "real_volume" in r.dtype.names and r["real_volume"] not in (0, None)
            else None
        )
        return OHLCVBar(
            timestamp=datetime.fromtimestamp(r["time"], tz=timezone.utc),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=tick_volume if tick_volume is not None else 0.0,
            spread=float(r["spread"]) if "spread" in r.dtype.names else None,
            tick_volume=tick_volume,
            real_volume=real_volume,
        )
