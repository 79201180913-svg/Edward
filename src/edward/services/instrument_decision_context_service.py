from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edward.services.decision_engine import InstrumentContextData


@dataclass(frozen=True, slots=True)
class InstrumentDecisionContextService:
    """Build the Decision Engine instrument context from T-Invest payloads."""

    def build(self, instrument: Any, trading_status: Any | None = None) -> InstrumentContextData:
        uid = _field(instrument, "uid", _field(instrument, "instrument_uid"))
        ticker = _field(instrument, "ticker")

        status = trading_status if trading_status is not None else instrument
        api_available = _bool(_field(status, "api_trade_available_flag", _field(instrument, "api_trade_available_flag", False)))
        buy_available = _bool(_field(instrument, "buy_available_flag", False))
        sell_available = _bool(_field(instrument, "sell_available_flag", False))
        trading_status_value = _field(status, "trading_status", _field(status, "status"))

        status_text = str(trading_status_value or "").upper()
        status_available = status_text not in {
            "SECURITY_TRADING_STATUS_NOT_AVAILABLE_FOR_TRADING",
            "NOT_AVAILABLE_FOR_TRADING",
        }
        available = bool(api_available and status_available and (buy_available or sell_available))

        return InstrumentContextData(
            instrument_uid=str(uid) if uid else None,
            ticker=str(ticker) if ticker else None,
            buy_available=buy_available,
            sell_available=sell_available,
            trading_status=str(trading_status_value) if trading_status_value is not None else None,
            available=available,
        )


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "yes", "да"}
    return bool(value)
