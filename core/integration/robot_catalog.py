"""Known trading-platform catalogue.

Entries are descriptive integration targets, not connected brokers and not
execution adapters.  Keeping this boundary explicit prevents a catalogue item
from being mistaken for an enabled trading robot.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class IntegrationStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    RESEARCH_ONLY = "RESEARCH_ONLY"


@dataclass(frozen=True)
class TradingPlatform:
    identifier: str
    name: str
    asset_classes: Tuple[str, ...]
    capabilities: Tuple[str, ...]
    status: IntegrationStatus
    notes: str


KNOWN_TRADING_PLATFORMS: Tuple[TradingPlatform, ...] = (
    TradingPlatform(
        identifier="metatrader_ea",
        name="MetaTrader Expert Advisors",
        asset_classes=("FOREX", "CFD"),
        capabilities=("chart_automation", "strategy_execution"),
        status=IntegrationStatus.NOT_CONFIGURED,
        notes="No EA bridge is bundled; real execution remains disabled.",
    ),
    TradingPlatform(
        identifier="freqtrade",
        name="Freqtrade",
        asset_classes=("CRYPTO",),
        capabilities=("strategy_research", "backtesting", "optimisation"),
        status=IntegrationStatus.RESEARCH_ONLY,
        notes="Requires a separately configured local Freqtrade instance.",
    ),
    TradingPlatform(
        identifier="hummingbot",
        name="Hummingbot",
        asset_classes=("CRYPTO",),
        capabilities=("market_making", "arbitrage"),
        status=IntegrationStatus.NOT_CONFIGURED,
        notes="Requires exchange connectivity and bid/ask or order-book data.",
    ),
    TradingPlatform(
        identifier="quantconnect_lean",
        name="QuantConnect LEAN",
        asset_classes=("FOREX", "CRYPTO", "EQUITY", "FUTURES"),
        capabilities=("quant_research", "backtesting"),
        status=IntegrationStatus.RESEARCH_ONLY,
        notes="No LEAN engine or data subscription is configured by this project.",
    ),
    TradingPlatform(
        identifier="cryptohopper",
        name="Cryptohopper",
        asset_classes=("CRYPTO",),
        capabilities=("automation", "strategy_configuration"),
        status=IntegrationStatus.NOT_CONFIGURED,
        notes="No account or API integration is configured.",
    ),
)


def list_known_trading_platforms() -> Tuple[TradingPlatform, ...]:
    """Return the static catalogue without connecting to an external service."""
    return KNOWN_TRADING_PLATFORMS
