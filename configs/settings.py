"""
Configuration centralisée de l'application.

Toutes les valeurs sensibles (credentials MT5, DB) sont chargées depuis
l'environnement (.env). Aucun secret ne doit être hardcodé ici.
"""
from enum import Enum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class BrokerBackend(str, Enum):
    """
    Détermine quel adaptateur MT5 est utilisé.

    - NATIVE : le package `MetaTrader5` est installé localement et un
      terminal MT5 tourne sur cette même machine (Windows uniquement).
    - MOCK   : aucun terminal réel n'est requis. Utilisé pour les tests,
      la CI, et le développement sur macOS/Linux.
    - BRIDGE : réservé pour une future implémentation pont réseau (RPC)
      vers une machine Windows distante hébergeant le terminal MT5.
      Non implémenté à l'Étape 1 — lève NotImplementedError si sélectionné.
    """

    NATIVE = "native"
    MOCK = "mock"
    BRIDGE = "bridge"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_env: AppEnv = AppEnv.DEVELOPMENT
    log_level: str = "INFO"
    app_name: str = "Adaptive Trading Intelligence Platform"

    # --- MT5 ---
    broker_backend: BrokerBackend = BrokerBackend.MOCK
    mt5_path: str | None = None
    mt5_login: int | None = None
    mt5_password: str | None = Field(default=None, repr=False)
    mt5_server: str | None = None
    mt5_broker_timezone: str = "UTC"

    # --- Database ---
    database_url: str = "postgresql+psycopg://atip:atip@localhost:5433/atip"

    # --- Safety ---
    # Verrou explicite : même en cas de bug ailleurs, ce flag doit rester
    # False pour que toute tentative d'exécution soit bloquée à l'Étape 1.
    trading_execution_enabled: bool = False

    # Étape 2 : garde-fou pour POST /data/collect — désactivé par défaut pour
    # ne pas exposer publiquement un endpoint capable de déclencher une
    # collecte massive (même sans risque de trading, c'est un risque de charge/coût).
    data_collection_api_enabled: bool = False

    @field_validator(
        "mt5_path", "mt5_login", "mt5_password", "mt5_server", mode="before"
    )
    @classmethod
    def blank_string_becomes_none(cls, v):
        """
        Un champ MT5 optionnel laissé vide dans .env (ex: MT5_LOGIN=) arrive
        ici comme chaîne vide "", que Pydantic refuse pour un champ int | None.
        On normalise "" en None avant validation, pour que .env.example reste
        utilisable tel quel sans que chaque champ optionnel doive être commenté.
        """
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    def __repr__(self) -> str:  # évite toute fuite accidentelle de secrets dans les logs
        return (
            f"Settings(app_env={self.app_env}, broker_backend={self.broker_backend}, "
            f"trading_execution_enabled={self.trading_execution_enabled})"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
