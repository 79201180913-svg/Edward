from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from edward.api.tinvest_adapter_client import TInvestAdapterClient
from edward.services.contract_evidence_mapper_v081 import (
    map_dividend,
    map_fundamentals,
    map_insider,
    map_news,
    map_order_book,
    map_risk_rates,
    map_signal,
    map_trades,
)


@dataclass(frozen=True, slots=True)
class ContractAnalysisDataV081:
    fundamentals: Any = None
    order_book: Any = None
    trades: tuple[Any, ...] = ()
    signals: tuple[Any, ...] = ()
    dividends: Any = None
    insider_transactions: tuple[Any, ...] = ()
    risk_data: Any = None
    reports: tuple[Any, ...] = ()
    news: tuple[Any, ...] = ()
    session_name: str | None = None
    fetched_sources: tuple[str, ...] = ()
    failed_sources: tuple[str, ...] = ()


class ContractAnalysisDataServiceV081:
    """Best-effort collection of contract-backed inputs for v0.8.1 analysis."""

    def __init__(self, client: TInvestAdapterClient) -> None:
        self.client = client

    @staticmethod
    def _first(payload: Any, *keys: str) -> Any:
        if not isinstance(payload, dict):
            return None
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value[0] if value else None
            if value is not None:
                return value
        return None

    @staticmethod
    def _many(payload: Any, *keys: str) -> list[Any]:
        if not isinstance(payload, dict):
            return []
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []

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
                date = cls._parse_dt(day.get("date")) if isinstance(day, dict) else None
                if date is not None and date.date() != now.date():
                    continue
                if isinstance(day, dict) and not day.get("is_trading_day", True):
                    return "UNKNOWN"
                if not isinstance(day, dict):
                    continue
                ranges = (
                    ("CLEARING", "clearing_start_time", "clearing_end_time"),
                    ("PREMARKET", "premarket_start_time", "premarket_end_time"),
                    ("OPENING_AUCTION", "opening_auction_start_time", "opening_auction_end_time"),
                    ("CLOSING_AUCTION", "closing_auction_start_time", "closing_auction_end_time"),
                    ("EVENING", "evening_start_time", "evening_end_time"),
                    ("REGULAR", "start_time", "end_time"),
                )
                for name, start_key, end_key in ranges:
                    start = cls._parse_dt(day.get(start_key))
                    end = cls._parse_dt(day.get(end_key))
                    if start is not None and end is not None and start <= now <= end:
                        return name
        return None

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

        raw_fundamentals = call("fundamentals", lambda: self.client.get_asset_fundamentals(instrument_uid), {})
        raw_order_book = call("order_book", lambda: self.client.get_order_book(instrument_uid, 10), {})
        raw_trades = call("last_trades", lambda: self.client.get_last_trades(instrument_uid, start, now), {})
        raw_signals = call("signals", lambda: self.client.get_signals(instrument_uid=instrument_uid, from_dt=start, to_dt=now), {})
        raw_dividends = call("dividends", lambda: self.client.get_dividends(instrument_uid, start, now), {})
        raw_insiders = call("insiders", lambda: self.client.get_insider_deals(instrument_uid, 100), {})
        raw_risk = call("risk_rates", lambda: self.client.get_risk_rates([instrument_uid]), {})
        raw_reports = call("reports", lambda: self.client.get_asset_reports(instrument_uid, start, now + timedelta(days=90)), {})
        raw_news = call("news", lambda: self.client.get_news(1000), {})
        raw_schedules = call("trading_schedules", lambda: self.client.get_trading_schedules(from_dt=now - timedelta(days=1), to_dt=now + timedelta(days=1)), {})

        fundamentals_raw = self._first(raw_fundamentals, "fundamentals", "statistics")
        order_book_raw = raw_order_book if raw_order_book else None
        trades_raw = self._many(raw_trades, "trades")
        signals_raw = self._many(raw_signals, "signals")
        dividends_raw = self._many(raw_dividends, "dividends")
        insiders_raw = self._many(raw_insiders, "insider_deals")
        reports_raw = self._many(raw_reports, "events")
        news_raw = [item for item in self._many(raw_news, "items", "news")]

        mapped_news = tuple(map_news(item) for item in news_raw)
        relevant_news = tuple(
            item for item in mapped_news
            if not item.get("instrument_id")
            or str(instrument_uid) in {str(value) for value in (item.get("instrument_id") or []) if isinstance(value, str)}
            or any(
                isinstance(link, dict)
                and str(instrument_uid) == str(((link.get("instrument") or {}).get("instrument_uid")))
                for link in (item.get("instrument_id") or ())
            )
        )

        return ContractAnalysisDataV081(
            fundamentals=map_fundamentals(fundamentals_raw) if fundamentals_raw is not None else None,
            order_book=map_order_book(order_book_raw) if order_book_raw else None,
            trades=tuple(map_trades({"trades": trades_raw})),
            signals=tuple(map_signal(item) for item in signals_raw),
            dividends=map_dividend(dividends_raw[0]) if dividends_raw else None,
            insider_transactions=tuple(map_insider(item) for item in insiders_raw),
            risk_data=map_risk_rates(raw_risk),
            reports=tuple(reports_raw),
            news=relevant_news,
            session_name=self._current_session(raw_schedules, now),
            fetched_sources=tuple(fetched),
            failed_sources=tuple(failed),
        )


__all__ = ["ContractAnalysisDataV081", "ContractAnalysisDataServiceV081"]
