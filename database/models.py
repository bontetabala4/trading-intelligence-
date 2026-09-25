"""
Modèles SQLAlchemy.

Étape 1 : Asset, MarketData, DataQualityEvent (schéma minimal).
Étape 2 : Asset enrichi (specs contrat), MarketData enrichi (tick_volume/
real_volume/source), IngestionEvent (suivi des collectes historiques).
Extension additive uniquement — aucune colonne Étape 1 supprimée.
"""
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(64), nullable=True)
    broker: Mapped[str] = mapped_column(String(64), nullable=False, default="mt5")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- Étape 2 : spécifications de contrat, optionnelles (dépendent du broker/instrument) ---
    base_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quote_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tick_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    tick_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    point: Mapped[float | None] = mapped_column(Float, nullable=True)
    digits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_step: Mapped[float | None] = mapped_column(Float, nullable=True)

    market_data: Mapped[list["MarketData"]] = relationship(back_populates="asset")
    quality_events: Mapped[list["DataQualityEvent"]] = relationship(back_populates="asset")
    ingestion_events: Mapped[list["IngestionEvent"]] = relationship(back_populates="asset")


class MarketData(Base):
    __tablename__ = "market_data"
    __table_args__ = (
        UniqueConstraint("asset_id", "timeframe", "timestamp", name="uq_market_data_bar"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    # Conservé pour compat Étape 1 (chemin MarketObserver / market-snapshot).
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    # --- Étape 2 : distinction tick_volume / real_volume (jamais inventés — NULL si absent) ---
    tick_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    real_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="mt5")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset: Mapped["Asset"] = relationship(back_populates="market_data")


class DataQualityEvent(Base):
    __tablename__ = "data_quality_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    issues: Mapped[str | None] = mapped_column(String, nullable=True)  # JSON sérialisé
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset: Mapped["Asset"] = relationship(back_populates="quality_events")


class IngestionEvent(Base):
    """
    Étape 2 (section 17/28) — trace chaque exécution du HistoricalDataCollector :
    statut, plage demandée, compteurs de lignes, durée, erreur éventuelle.
    Sert de base à GET /data/status et au rapport de non-régression.
    """

    __tablename__ = "ingestion_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # IDLE/RUNNING/SUCCESS/PARTIAL/FAILED
    range_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    range_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rows_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset: Mapped["Asset"] = relationship(back_populates="ingestion_events")
