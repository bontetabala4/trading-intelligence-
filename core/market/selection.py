"""
MarketSelection — modèle de validation stricte de la sélection utilisateur.

Le système refuse toute configuration incohérente dès l'entrée (fail fast),
avant même de tenter une connexion broker.
"""
from enum import Enum

from pydantic import BaseModel, field_validator

from brokers.base.interface import Timeframe


class AssetClass(str, Enum):
    FOREX = "forex"
    INDICES = "indices"
    METALS = "metals"
    STOCKS = "stocks"
    BONDS_RATES = "bonds_rates"
    COMMODITIES = "commodities"
    CRYPTO = "crypto"
    FUTURES = "futures"
    CURRENCIES_FX = "currencies_fx"
    OTHER = "other"


class TradingStyle(str, Enum):
    SCALPING = "scalping"
    DAY_TRADING = "day_trading"
    SWING_TRADING = "swing_trading"
    POSITION_TRADING = "position_trading"


class Mode(str, Enum):
    ANALYSIS_ONLY = "analysis_only"
    BACKTEST = "backtest"
    PAPER_TRADING = "paper_trading"
    DEMO = "demo"
    LIVE = "live"


# Styles de trading cohérents avec chaque timeframe. Une incohérence n'est
# pas bloquée (choix produit), mais réservée pour un futur warning côté API.
_STYLE_TIMEFRAME_HINTS = {
    TradingStyle.SCALPING: {Timeframe.M1, Timeframe.M5},
    TradingStyle.DAY_TRADING: {Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1},
    TradingStyle.SWING_TRADING: {Timeframe.H1, Timeframe.H4, Timeframe.D1},
    TradingStyle.POSITION_TRADING: {Timeframe.D1, Timeframe.W1},
}


class MarketSelection(BaseModel):
    asset_class: AssetClass
    symbol: str
    trading_style: TradingStyle
    timeframe: Timeframe
    mode: Mode = Mode.ANALYSIS_ONLY

    @field_validator("symbol")
    @classmethod
    def symbol_must_be_uppercase_and_nonempty(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Le symbole ne peut pas être vide.")
        return v

    @field_validator("mode")
    @classmethod
    def block_live_mode_at_this_stage(cls, v: Mode) -> Mode:
        """
        Garde-fou produit pour l'Étape 1 : LIVE n'est pas encore autorisé,
        quel que soit ce que l'utilisateur envoie. Ce n'est pas une simple
        valeur par défaut — c'est un refus explicite.
        """
        if v == Mode.LIVE:
            raise ValueError(
                "Le mode LIVE n'est pas disponible à l'Étape 1. "
                "Utilisez ANALYSIS_ONLY, BACKTEST, PAPER_TRADING ou DEMO."
            )
        return v

    def style_matches_timeframe(self) -> bool:
        """Indicatif seulement — n'invalide pas la sélection."""
        return self.timeframe in _STYLE_TIMEFRAME_HINTS.get(self.trading_style, set())
