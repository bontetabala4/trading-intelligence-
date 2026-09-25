"""
BrokerInterface — contrat abstrait que tout adaptateur de broker doit respecter.

Étape 1 : seul MT5Adapter (et son double MockMT5Adapter) implémente cette
interface. Les futurs adaptateurs (IBKR, OANDA, Futures, Crypto) suivront
le même contrat sans que le reste du système n'ait à changer.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"


@dataclass(frozen=True)
class OHLCVBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    spread: float | None = None
    # Étape 2 : MT5 distingue tick_volume (nombre de variations de prix) et
    # real_volume (volume réel, souvent absent en Forex/CFD — reste NULL en
    # base plutôt qu'inventé). `volume` (ci-dessus) reste calculé à partir de
    # tick_volume pour ne pas casser le chemin Étape 1 (MarketObserver).
    tick_volume: float | None = None
    real_volume: float | None = None


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str
    exists: bool
    tradable: bool
    description: str | None = None
    currency_base: str | None = None
    currency_quote: str | None = None
    digits: int | None = None


@dataclass(frozen=True)
class AccountInfo:
    login: int
    server: str
    balance: float
    equity: float
    currency: str
    leverage: int
    trade_allowed: bool


@dataclass(frozen=True)
class TerminalInfo:
    connected: bool
    name: str | None = None
    build: int | None = None
    trade_allowed: bool = False


@dataclass(frozen=True)
class OrderRequest:
    """Réservé pour l'exécution future. Non utilisé à l'Étape 1."""

    symbol: str
    volume: float
    side: str


@dataclass(frozen=True)
class OrderResult:
    """Réservé pour l'exécution future. Non utilisé à l'Étape 1."""

    success: bool
    order_id: int | None
    message: str


class BrokerConnectionError(RuntimeError):
    """Levée quand la connexion au broker échoue ou est indisponible."""


class ExecutionDisabledError(RuntimeError):
    """
    Levée systématiquement par execute_order() à l'Étape 1.

    Ce n'est pas un bug — c'est un garde-fou intentionnel. L'exécution
    réelle sera activée dans une étape future, derrière un Risk Engine
    ayant droit de veto, et seulement si Settings.trading_execution_enabled
    est explicitement True.
    """


class BrokerInterface(ABC):
    """Contrat que tout adaptateur de broker doit implémenter."""

    @abstractmethod
    def connect(self) -> None:
        """Initialise la connexion au broker. Lève BrokerConnectionError en cas d'échec."""

    @abstractmethod
    def disconnect(self) -> None:
        """Ferme proprement la connexion."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Vérifie l'état courant de la connexion (health check actif, pas juste un flag)."""

    @abstractmethod
    def get_terminal_info(self) -> TerminalInfo:
        """Retourne l'état du terminal broker."""

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """Retourne les informations du compte connecté."""

    @abstractmethod
    def list_symbols(self) -> list[str]:
        """Liste les symboles disponibles chez ce broker."""

    @abstractmethod
    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """Vérifie l'existence et la tradabilité d'un symbole."""

    @abstractmethod
    def get_ohlcv(
        self, symbol: str, timeframe: Timeframe, count: int = 500
    ) -> list[OHLCVBar]:
        """Récupère les N dernières bougies OHLCV pour un symbole/timeframe."""

    @abstractmethod
    def get_ohlcv_range(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[OHLCVBar]:
        """
        Récupère les bougies OHLCV sur une plage [start, end] (bornes UTC,
        timezone-aware). Utilisé par HistoricalDataCollector (Étape 2) pour
        la collecte historique et incrémentale — distinct de get_ohlcv() qui
        sert l'observation instantanée (Étape 1, MarketObserver).

        Peut retourner une liste vide si aucune donnée sur la plage (ex:
        marché fermé) — ce n'est pas une erreur en soi.
        """

    def execute_order(self, order: OrderRequest) -> OrderResult:
        """
        STUB ARCHITECTURAL — DÉSACTIVÉ À L'ÉTAPE 1.

        Existe pour compléter le contrat d'interface en vue des étapes
        futures (Risk Engine → Execution Engine). Toute tentative d'appel
        lève ExecutionDisabledError, quel que soit l'adaptateur concret.
        """
        raise ExecutionDisabledError(
            "Exécution désactivée : mode ANALYSIS_ONLY obligatoire à l'Étape 1."
        )
