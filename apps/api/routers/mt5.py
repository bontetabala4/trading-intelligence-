"""GET /mt5/status, GET /mt5/account"""
from fastapi import APIRouter, Depends, HTTPException

from apps.api.dependencies import get_broker
from brokers.base.interface import BrokerConnectionError, BrokerInterface

router = APIRouter(prefix="/mt5", tags=["mt5"])


@router.get("/status")
def mt5_status(broker: BrokerInterface = Depends(get_broker)) -> dict:
    terminal = broker.get_terminal_info()
    return {
        "status": "success",
        "data": {
            "connected": terminal.connected,
            "name": terminal.name,
            "build": terminal.build,
            "trade_allowed": terminal.trade_allowed,
        },
    }


@router.get("/account")
def mt5_account(broker: BrokerInterface = Depends(get_broker)) -> dict:
    try:
        account = broker.get_account_info()
    except BrokerConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "success",
        "data": {
            "login": account.login,
            "server": account.server,
            "balance": account.balance,
            "equity": account.equity,
            "currency": account.currency,
            "leverage": account.leverage,
            "trade_allowed": account.trade_allowed,
        },
    }
