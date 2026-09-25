"""
Dependency Injection FastAPI — instancie le broker adéquat selon
Settings.broker_backend, injecté dans les routes plutôt que codé en dur.
"""
from functools import lru_cache

from sqlalchemy.orm import Session

from brokers.base.interface import BrokerConnectionError, BrokerInterface
from brokers.mt5.mock_adapter import MockMT5Adapter
from configs.settings import BrokerBackend, get_settings
from core.data.collector import HistoricalDataCollector
from core.data.quality_engine import DataQualityEngine
from core.market.observer import MarketObserver


@lru_cache
def get_broker() -> BrokerInterface:
    settings = get_settings()

    if settings.broker_backend == BrokerBackend.MOCK:
        broker = MockMT5Adapter()
    elif settings.broker_backend == BrokerBackend.NATIVE:
        # Import différé : évite tout crash sur machine sans package MetaTrader5.
        from brokers.mt5.adapter import MT5Adapter

        broker = MT5Adapter(
            path=settings.mt5_path,
            login=settings.mt5_login,
            password=settings.mt5_password,
            server=settings.mt5_server,
        )
    elif settings.broker_backend == BrokerBackend.BRIDGE:
        raise NotImplementedError(
            "BrokerBackend.BRIDGE n'est pas encore implémenté (réservé étape future : "
            "pont réseau vers une machine Windows distante hébergeant MT5)."
        )
    else:
        raise ValueError(f"BrokerBackend inconnu : {settings.broker_backend}")

    if not broker.is_connected():
        try:
            broker.connect()
        except BrokerConnectionError:
            # On laisse l'appelant décider quoi faire (ex: /mt5/status doit
            # pouvoir répondre DISCONNECTED sans planter toute l'API).
            pass

    return broker


def get_quality_engine() -> DataQualityEngine:
    return DataQualityEngine()


def get_market_observer() -> MarketObserver:
    return MarketObserver(broker=get_broker(), quality_engine=get_quality_engine())


def get_collector(db: Session) -> HistoricalDataCollector:
    """
    Construit un HistoricalDataCollector lié à la session DB de la requête
    courante. N'est pas un simple `Depends()` autonome car il a besoin de
    `db` (fourni par get_db) — les routers l'appellent explicitement avec
    la session injectée plutôt que de le déclarer comme dépendance FastAPI
    imbriquée, pour garder une seule session par requête.
    """
    from database.repositories.asset_repository import AssetRepository
    from database.repositories.market_data_repository import MarketDataRepository

    return HistoricalDataCollector(
        broker=get_broker(),
        asset_repo=AssetRepository(db),
        market_data_repo=MarketDataRepository(db),
    )
