from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
import logging

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.services.contract_evidence_mapper_v081 import map_dividend, map_fundamentals, map_insider, map_instrument_risk, map_news, map_order_book, map_risk_rates, map_signal, map_trades

logger = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class ContractAnalysisDataV081:
    fundamentals: Any = None
    order_book: Any = None
    trades: tuple[Any, ...] = ()
    signals: tuple[Any, ...] = ()
    dividends: Any = None
    insider_transactions: tuple[Any, ...] = ()
    risk_data: Any = None
    instrument_risk_metadata: Any = None
    reports: tuple[Any, ...] = ()
    news: tuple[Any, ...] = ()
    session_name: str | None = None
    session_available: bool = False
    fetched_sources: tuple[str, ...] = ()
    failed_sources: tuple[str, ...] = ()
    unavailable_sources: tuple[str, ...] = ()

class ContractAnalysisDataServiceV081:
    """Best-effort collection of contract-backed inputs for v0.8.1 analysis."""
    def __init__(self, client: TInvestAdapterClient) -> None: self.client = client
    @staticmethod
    def _first(payload: Any, *keys: str) -> Any:
        if isinstance(payload, list): return payload[0] if payload else None
        if not isinstance(payload, dict): return None
        normalized = {str(key).replace("_", "").lower(): key for key in payload}
        for key in keys:
            for candidate in (key, key.replace("_", "")):
                if candidate in payload:
                    value = payload[candidate]; return value[0] if isinstance(value, list) and value else value
            source_key = normalized.get(key.replace("_", "").lower())
            if source_key is not None:
                value = payload[source_key]; return value[0] if isinstance(value, list) and value else value
        return None
    @classmethod
    def _first_recursive(cls, payload: Any, *keys: str, max_depth: int = 3) -> Any:
        value = cls._first(payload, *keys)
        if value is not None: return value
        if max_depth <= 0 or not isinstance(payload, dict): return None
        for wrapper in ("response", "data", "result", "payload"):
            nested = cls._first(payload, wrapper)
            if nested is None or nested is payload: continue
            value = cls._first_recursive(nested, *keys, max_depth=max_depth - 1)
            if value is not None: return value
        return None
    @classmethod
    def _many_recursive(cls, payload: Any, *keys: str, max_depth: int = 6) -> list[Any]:
        if isinstance(payload, list): return payload
        if not isinstance(payload, dict) or max_depth < 0: return []
        normalized = {str(key).replace("_", "").lower(): key for key in payload}
        for key in keys:
            source_key = normalized.get(key.replace("_", "").lower())
            if source_key is not None:
                value = payload[source_key]
                if isinstance(value, list): return value
                nested = cls._many_recursive(value, *keys, max_depth=max_depth - 1)
                if nested: return nested
        for wrapper in ("response", "data", "result", "payload"):
            source_key = normalized.get(wrapper)
            if source_key is None: continue
            nested = cls._many_recursive(payload[source_key], *keys, max_depth=max_depth - 1)
            if nested: return nested
        return []
    @staticmethod
    def _many(payload: Any, *keys: str) -> list[Any]:
        if isinstance(payload, list): return payload
        if not isinstance(payload, dict): return []
        normalized = {str(key).replace("_", "").lower(): key for key in payload}
        for key in keys:
            for candidate in (key, key.replace("_", "")):
                if candidate in payload:
                    value = payload[candidate]; return value if isinstance(value, list) else []
            source_key = normalized.get(key.replace("_", "").lower())
            if source_key is not None:
                value = payload[source_key]; return value if isinstance(value, list) else []
        return []
    @staticmethod
    def _field(payload: Any, name: str, default: Any = None) -> Any:
        if not isinstance(payload, dict): return default
        if name in payload: return payload[name]
        compact = name.replace("_", "").lower()
        for key, value in payload.items():
            if str(key).replace("_", "").lower() == compact: return value
        return default
    @classmethod
    def _map_report(cls, report: Any) -> Any:
        if not isinstance(report, dict): return report
        return {"instrument_id": cls._field(report, "instrument_id"), "report_date": cls._field(report, "report_date"), "period_year": cls._field(report, "period_year"), "period_num": cls._field(report, "period_num"), "period_type": cls._field(report, "period_type"), "created_at": cls._field(report, "created_at")}
    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if isinstance(value, datetime): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00")); return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError: return None
        return None
    @classmethod
    def _current_session(cls, payload: Any, now: datetime) -> str | None:
        for exchange in cls._many(payload, "exchanges", "schedules", "items"):
            for day in cls._many(exchange, "days"):
                if not isinstance(day, dict): continue
                date = cls._parse_dt(cls._field(day, "date"))
                if date is not None and date.date() != now.date(): continue
                if not cls._field(day, "is_trading_day", True): return "UNKNOWN"
                for name, start_key, end_key in (("CLEARING", "clearing_start_time", "clearing_end_time"), ("PREMARKET", "premarket_start_time", "premarket_end_time"), ("OPENING_AUCTION", "opening_auction_start_time", "opening_auction_end_time"), ("CLOSING_AUCTION", "closing_auction_start_time", "closing_auction_end_time"), ("EVENING", "evening_start_time", "evening_end_time"), ("REGULAR", "start_time", "end_time")):
                    start, end = cls._parse_dt(cls._field(day, start_key)), cls._parse_dt(cls._field(day, end_key))
                    if start is not None and end is not None and start <= now <= end: return name
        return None
    @staticmethod
    def _instrument_candidate(payload: Any) -> Any:
        if not isinstance(payload, dict): return payload
        for key in ("instrument", "instruments", "response", "data", "result"):
            value = payload.get(key)
            if isinstance(value, dict): return value
            if isinstance(value, list) and value: return value[0]
        return payload
    def collect(self, instrument_uid: str) -> ContractAnalysisDataV081:
        now = datetime.now(timezone.utc); start = now - timedelta(days=365)
        fetched: list[str] = []; failed: list[str] = []; unavailable: list[str] = []
        def call(name: str, fn, default=None):
            try: value = fn(); fetched.append(name); return value
            except Exception: failed.append(name); return default
        raw_instrument = call("instrument", lambda: self.client.get_instrument(instrument_uid), {}) if hasattr(self.client, "get_instrument") else {}
        raw_fundamentals = call("fundamentals", lambda: self.client.get_asset_fundamentals(instrument_uid), {})
        raw_order_book = call("order_book", lambda: self.client.get_order_book(instrument_uid, 10), {})
        raw_trades = call("last_trades", lambda: self.client.get_last_trades(instrument_uid, start, now), {})
        raw_signals = call("signals", lambda: self.client.get_signals(instrument_uid=instrument_uid, from_dt=start, to_dt=now), {})
        raw_dividends = call("dividends", lambda: self.client.get_dividends(instrument_uid, start, now), {})
        raw_insiders = call("insiders", lambda: self.client.get_insider_deals(instrument_uid, 100), {})
        raw_risk = call("risk_rates", lambda: self.client.get_risk_rates([instrument_uid]), {})
        raw_reports = call("reports", lambda: self.client.get_asset_reports(instrument_uid, start, now + timedelta(days=90)), {})
        raw_news = call("news", lambda: self.client.get_news(1000), {})
        raw_schedules = call("trading_schedules", lambda: self.client.get_trading_schedules(from_dt=now, to_dt=now + timedelta(days=2)), {})
        fundamentals_raw = self._first_recursive(raw_fundamentals, "fundamentals", "statistics", "asset_fundamentals")
        reports_raw = self._many_recursive(raw_reports, "events", "reports")
        insiders_raw = self._many_recursive(raw_insiders, "insider_deals", "insiders")
        dividends_raw = self._many_recursive(raw_dividends, "dividends")
        signals_raw = self._many_recursive(raw_signals, "signals")
        news_raw = self._many_recursive(raw_news, "items", "news")
        mapped_instrument_risk = map_instrument_risk(self._instrument_candidate(raw_instrument)); mapped_fundamentals = map_fundamentals(fundamentals_raw); mapped_order_book = map_order_book(raw_order_book); mapped_risk_rates = map_risk_rates(raw_risk)
        mapped_news = tuple(map_news(item) for item in news_raw)
        relevant_news = tuple(item for item in mapped_news if not item.get("instrument_id") or str(instrument_uid) in {str(value) for value in (item.get("instrument_id") or []) if isinstance(value, str)} or any(isinstance(link, dict) and str(instrument_uid) == str(((link.get("instrument") or {}).get("instrument_uid"))) for link in (item.get("instrument_id") or ())))
        session_name = self._current_session(raw_schedules, now); session_available = "trading_schedules" in fetched and session_name is not None
        if raw_fundamentals not in ({}, None) and mapped_fundamentals is None: unavailable.append("fundamentals")
        if raw_risk not in ({}, None) and mapped_risk_rates is None: unavailable.append("risk_rates_mapping")
        if raw_instrument not in ({}, None) and mapped_instrument_risk is None: unavailable.append("instrument")
        if self._many_recursive(raw_schedules, "exchanges", "schedules", "items") and session_name is None: unavailable.append("trading_schedules")
        if raw_reports not in ({}, None) and not reports_raw: unavailable.append("reports")
        if raw_insiders not in ({}, None) and not insiders_raw: unavailable.append("insiders")
        if raw_news not in ({}, None) and not news_raw: unavailable.append("news")
        return ContractAnalysisDataV081(mapped_fundamentals, mapped_order_book, tuple(map_trades(raw_trades)), tuple(map_signal(item) for item in signals_raw), map_dividend(dividends_raw[0]) if dividends_raw else None, tuple(map_insider(item) for item in insiders_raw), mapped_risk_rates, mapped_instrument_risk, tuple(self._map_report(item) for item in reports_raw), relevant_news, session_name if session_available else None, session_available, tuple(fetched), tuple(failed), tuple(dict.fromkeys(unavailable)))

__all__ = ["ContractAnalysisDataV081", "ContractAnalysisDataServiceV081"]