from enum import Enum

class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"

class ExecutionStatus(str, Enum):
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class MT5RetCode(int, Enum):
    SUCCESS = 10009
    REQUOTE = 10004
    PRICE_OFF = 10014
    NO_MONEY = 10019
    SLIPPAGE = 10021