from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
import logging

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.services.contract_evidence_mapper_v081 import (
    map_dividend,
    map_fundamentals,
    map_insider,
    map_instrument_risk,
    map_news,
    map_order_book,
    map_risk_rates,
    map_signal,
    map_trades,
)


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

    def __init__(self, client: TInvestAdapterClient) -> None:
        self.client = client

    @staticmethod
    def _first(payload: Any, *keys: str) -> Any:
        if isinstance(payload, list):
            return payload[0] if payload else None
        if not isinstance(payload, dict):
            return None
        normalized = {str(key).replace("_", "").lower(): key for key in payload}
        for key in keys:
            for candidate in (key, key.replace("_", "")):
                if candidate in payload:
                    value = payload[candidate]
                    return value[0] if isinstance(value, list) and value else value
            source_key = normalized.get(key.replace("_", "").lower())
            if source_key is not None:
                value = payload[source_key]
                return value[0] if isinstance(value, list) and value else value
        return None

    @staticmethod
    def _many(payload: Any, *keys: str) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        normalized = {str(key).replace("_", "").lower(): key for key in payload}
        for key in keys:
            for candidate in (key, key.replace("_", "")):
                if candidate in payload:
                    value = payload[candidate]
                    return value if isinstance(value, list) else []
            source_key = normalized.get(key.replace("_", "").lower())
            if source_key is not None:
                value = payload[source_key]
                return value if isinstance(value, list) else []
        return []

    @staticmethod
    def _field(payload: Any, name: str, default: Any = None) -> Any:
        if not isinstance(payload, dict):
            return default
        if name in payload:
            return payload[name]
        compact = name.replace("_", "").lower()
        for key, value in payload.items():
            if str(key).replace("_", "").lower() == compact:
                return value
        return default

    @classmethod
    def _map_report(cls, report: Any) -> Any:
        if not isinstance(report, dict):
            return report
        return {
            "instrument_id": cls._field(report, "instrument_id"),
            "report_date": cls._field(report, "report_date"),
            "period_year": cls._field(report, "period_year"),
            "period_num": cls._field(report, "period_num"),
            "period_type": cls._field(report, "period_type"),
            "created_at": cls._field(report, "created_at"),
        }

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    @classmethod
    def _current_session(cls, payload: Any, now: datetime) -> str | None:
        exchanges = cls._many(payload, "exchanges", "schedules", "items")
        for exchange in exchanges:
            for day in cls._many(exchange, "days"):
                if not isinstance(day, dict):
                    continue
                date = cls._parse_dt(cls._field(day, "date"))
                if date is not None and date.date() != now.date():
                    continue
                if not cls._field(day, "is_trading_day", True):
                    return "UNKNOWN"
                ranges = (
                    ("CLEARING", "clearing_start_time", "clearing_end_time"),
                    ("PREMARKET", "premarket_start_time", "premarket_end_time"),
                    ("OPENING_AUCTION", "opening_auction_start_time", "opening_auction_end_time"),
                    ("CLOSING_AUCTION", "closing_auction_start_time", "closing_auction_end_time"),
                    ("EVENING", "evening_start_time", "evening_end_time"),
                    ("REGULAR", "start_time", "end_time"),
                )
                for name, start_key, end_key in ranges:
                    start = cls._parse_dt(cls._field(day, start_key))
                    end = cls._parse_dt(cls._field(day, end_key))
                    if start is not None and end is not None and start <= now <= end:
                        return name
        return None

    @staticmethod
    def _instrument_candidate(payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        for key in ("instrument", "instruments", "response", "data", "result"):
            value = payload.get(key)
            if isinstance(value, dict):
                return value
            if isinstance(value, list) and value:
                return value[0]
        return payload

    @staticmethod
    def _merge_risk_data(risk_rates: Any, instrument_risk: Any) -> Any:
        """Compatibility hook: keep GetRiskRates isolated from Instrument metadata."""
        return risk_rates

    def collect(self, instrument_uid: str) -> ContractAnalysisDataV081:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=365)
        fetched: list[str] = []
        failed: list[str] = []

        def call(name: str, fn, default=None):
            try:
                value = fn()
                fetched.append(name)
                return value
            except Exception:
                failed.append(name)
                return default

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

        fundamentals_raw = self._first(raw_fundamentals, "fundamentals", "statistics")
        reports_raw = self._many(raw_reports, "events", "reports")
        insiders_raw = self._many(raw_insiders, "insider_deals", "insiders")
        dividends_raw = self._many(raw_dividends, "dividends")
        signals_raw = self._many(raw_signals, "signals")
        news_raw = self._many(raw_news, "items", "news")

        instrument_candidate = self._instrument_candidate(raw_instrument)
        mapped_instrument_risk = map_instrument_risk(instrument_candidate)
        logger.warning(
            "[V081 INSTRUMENT RISK METADATA] instrument_uid=%s raw_type=%s raw_keys=%s mapped=%r",
            instrument_uid,
            type(instrument_candidate).__name__,
            list(instrument_candidate.keys()) if isinstance(instrument_candidate, dict) else None,
            mapped_instrument_risk,
        )
        mapped_fundamentals = map_fundamentals(fundamentals_raw)
        mapped_order_book = map_order_book(raw_order_book)
        mapped_risk_rates = map_risk_rates(raw_risk)
        mapped_news = tuple(map_news(item) for item in news_raw)
        relevant_news = tuple(
            item for item in mapped_news
            if not item.get("instrument_id")
            or str(instrument_uid) in {str(value) for value in (item.get("instrument_id") or []) if isinstance(value, str)}
            or any(isinstance(link, dict) and str(instrument_uid) == str(((link.get("instrument") or {}).get("instrument_uid"))) for link in (item.get("instrument_id") or ()))
        )
        session_name = self._current_session(raw_schedules, now)
        session_available = "trading_schedules" in fetched and session_name is not None

        if raw_fundamentals not in ({}, None) and mapped_fundamentals is None:
            failed.append("fundamentals_mapping")
        if raw_risk not in ({}, None) and mapped_risk_rates is None:
            failed.append("risk_rates_mapping")
        if raw_instrument not in ({}, None) and mapped_instrument_risk is None:
            failed.append("instrument_mapping")
        schedule_items = self._many(raw_schedules, "exchanges", "schedules", "items")
        if schedule_items and session_name is None:
            failed.append("trading_schedules_mapping")
        if raw_reports not in ({}, None) and not reports_raw:
            failed.append("reports_mapping")
        if raw_insiders not in ({}, None) and not insiders_raw:
            failed.append("insiders_mapping")
        if raw_news not in ({}, None) and not news_raw:
            failed.append("news_mapping")

        return ContractAnalysisDataV081(
            fundamentals=mapped_fundamentals,
            order_book=mapped_order_book,
            trades=tuple(map_trades(raw_trades)),
            signals=tuple(map_signal(item) for item in signals_raw),
            dividends=map_dividend(dividends_raw[0]) if dividends_raw else None,
            insider_transactions=tuple(map_insider(item) for item in insiders_raw),
            risk_data=mapped_risk_rates,
            instrument_risk_metadata=mapped_instrument_risk,
            reports=tuple(self._map_report(item) for item in reports_raw),
            news=relevant_news,
            session_name=session_name if session_available else None,
            session_available=session_available,
            fetched_sources=tuple(fetched),
            failed_sources=tuple(failed),
            unavailable_sources=(),
        )


__all__ = ["ContractAnalysisDataV081", "ContractAnalysisDataServiceV081"]
