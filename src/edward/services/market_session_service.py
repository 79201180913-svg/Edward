from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SESSION_CLOSE = 12
SESSION_OPEN = 13

@dataclass(frozen=True, slots=True)
class MarketSessionResult:
    status: str
    reason: str = ""
    instrument_uids: tuple[str, ...] = ()
    @property
    def is_open(self) -> bool: return self.status == "OPEN"
    @property
    def is_closed(self) -> bool: return self.status == "CLOSED"

class MarketSessionService:
    """Determines whether autonomous trading can proceed from T-Invest statuses."""
    def __init__(self, trading_status_gateway: Any) -> None:
        self._gateway = trading_status_gateway

    def check_positions(self, positions_response: Any) -> MarketSessionResult:
        instrument_uids = self._instrument_uids(positions_response)
        if not instrument_uids:
            return MarketSessionResult("OPEN", "NO_POSITIONS", ())
        return self.check_instruments(instrument_uids)

    def check_instruments(self, instrument_uids: list[str] | tuple[str, ...]) -> MarketSessionResult:
        uids = tuple(dict.fromkeys(str(uid) for uid in instrument_uids if str(uid).strip()))
        if not uids:
            return MarketSessionResult("OPEN", "NO_INSTRUMENTS", ())
        response = self._gateway.get_trading_statuses(list(uids))
        statuses = self._items(response, "trading_statuses")
        if not statuses:
            return MarketSessionResult("UNKNOWN", "MARKET_STATUS_EMPTY", uids)
        open_uids: list[str] = []
        closed_uids: list[str] = []
        unknown_uids: list[str] = []
        for item in statuses:
            uid = str(self._field(item, "instrument_uid", "") or "")
            status = self._normalize_status(self._field(item, "trading_status", None))
            api_available = self._bool(self._field(item, "api_trade_available_flag", False))
            if status == SESSION_OPEN and api_available:
                if uid: open_uids.append(uid)
            elif status == SESSION_CLOSE or (status == SESSION_OPEN and not api_available):
                if uid: closed_uids.append(uid)
            elif uid:
                unknown_uids.append(uid)
        if open_uids:
            return MarketSessionResult("OPEN", "API_TRADE_AVAILABLE", tuple(open_uids))
        if closed_uids and not unknown_uids:
            return MarketSessionResult("CLOSED", "NO_API_TRADE_AVAILABLE", tuple(closed_uids))
        if unknown_uids and not closed_uids:
            return MarketSessionResult("UNKNOWN", "MARKET_STATUS_UNDETERMINED", tuple(unknown_uids))
        if closed_uids:
            return MarketSessionResult("CLOSED", "NO_API_TRADE_AVAILABLE", tuple(closed_uids))
        return MarketSessionResult("UNKNOWN", "MARKET_STATUS_UNDETERMINED", uids)

    @classmethod
    def _instrument_uids(cls, response: Any) -> list[str]:
        return [str(cls._field(item, "instrument_uid", "") or "") for item in cls._items(response, "securities") if str(cls._field(item, "instrument_uid", "") or "")]

    @staticmethod
    def _field(value: Any, name: str, default: Any = None) -> Any:
        if isinstance(value, dict): return value.get(name, default)
        return getattr(value, name, default)

    @staticmethod
    def _items(value: Any, key: str) -> list[Any]:
        if value is None: return []
        raw = value.get(key, []) if isinstance(value, dict) else getattr(value, key, [])
        if raw is None: return []
        if isinstance(raw, (list, tuple)): return list(raw)
        try: return list(raw)
        except TypeError: return [raw]

    @staticmethod
    def _normalize_status(value: Any) -> int | None:
        try: return int(value)
        except (TypeError, ValueError): pass
        text = str(value or "").strip().upper()
        if text == "SESSION_CLOSE" or text.endswith("SESSION_CLOSE"): return SESSION_CLOSE
        if text == "SESSION_OPEN" or text.endswith("SESSION_OPEN"): return SESSION_OPEN
        return None

    @staticmethod
    def _bool(value: Any) -> bool:
        if isinstance(value, bool): return value
        if isinstance(value, str): return value.strip().lower() in {"true", "1", "yes"}
        return bool(value)

__all__ = ["MarketSessionResult", "MarketSessionService", "SESSION_CLOSE", "SESSION_OPEN"]
