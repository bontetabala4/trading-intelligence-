"""GET /markets, GET /markets/{symbol}"""
from fastapi import APIRouter, Depends, HTTPException

from apps.api.dependencies import get_broker
from brokers.base.interface import BrokerInterface

router = APIRouter(prefix="/markets", tags=["markets"])


@router.get("")
def list_markets(broker: BrokerInterface = Depends(get_broker)) -> dict:
    symbols = broker.list_symbols()
    return {"status": "success", "data": {"symbols": symbols, "count": len(symbols)}}


@router.get("/{symbol}")
def get_market(symbol: str, broker: BrokerInterface = Depends(get_broker)) -> dict:
    info = broker.get_symbol_info(symbol.upper())
    if not info.exists:
        raise HTTPException(status_code=404, detail=f"Symbole '{symbol}' introuvable chez ce broker.")

    return {
        "status": "success",
        "symbol": info.symbol,
        "data": {
            "exists": info.exists,
            "tradable": info.tradable,
            "description": info.description,
            "currency_base": info.currency_base,
            "currency_quote": info.currency_quote,
            "digits": info.digits,
        },
    }
