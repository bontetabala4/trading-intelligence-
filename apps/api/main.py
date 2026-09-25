"""Point d'entrée FastAPI — assemble les routers, logging, config."""
import logging

from fastapi import FastAPI

from apps.api.routers import data_pipeline, features, health, market_data, markets, mt5
from configs.settings import get_settings

from apps.api.routers import regime
from apps.api.routers import signals
from apps.api.routers import risk
from apps.api.routers import execution


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0-etape1",
        description="ATIP — Étape 1 : Fondation + Market Selection + MT5 Observer (READ ONLY)",
    )

    app.include_router(health.router)
    app.include_router(mt5.router)
    app.include_router(markets.router)
    app.include_router(market_data.router)
    app.include_router(data_pipeline.router)
    app.include_router(features.router)
    app.include_router(regime.router)
    app.include_router(signals.router)
    app.include_router(risk.router)
    app.include_router(execution.router)


    return app


app = create_app()
