from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from edward.services.contract_analysis_data_service_v081 import ContractAnalysisDataServiceV081
from edward.services.contract_evidence_mapper_v081 import (
    map_fundamentals,
    map_insider,
    map_order_book,
    map_risk_rates,
)


class RobustContractAnalysisDataServiceV081(ContractAnalysisDataServiceV081):
    """v0.8.1 collector with recursive contract-response discovery."""

    _DIRECT_FIELD_GROUPS = {
        "fundamentals": {
            "roe", "roic", "net_margin_mrq", "revenue_ttm", "free_cash_flow_ttm",
            "pe_ratio_ttm", "eps_change_five_years", "net_debt_to_ebitda",
            "one_year_annual_revenue_growth_rate", "current_ratio_mrq",
        },
        "risk_rates": {
            "long_risk_rate", "short_risk_rate", "dlong", "dshort",
            "dlong_client", "dshort_client",
        },
        "reports": {"report_date", "period_year", "period_num", "period_type"},
        "insiders": {"quantity", "direction", "investor_position", "percentage"},
        "news": {"id", "title", "source", "priority", "ts"},
        "signals": {"signal_id", "strategy_id", "direction", "initial_price"},
        "dividends": {"yield_value", "dividend_yield", "regularity", "declared_date"},
    }

    @classmethod
    def _walk(cls, value: Any, *, max_depth: int = 12):
        seen: set[int] = set()
        stack: list[tuple[Any, int]] = [(value, 0)]
        while stack:
            current, depth = stack.pop()
            if current is None or depth > max_depth:
                continue
            if isinstance(current, (Mapping, list, tuple)):
                identity = id(current)
                if identity in seen:
                    continue
                seen.add(identity)
            yield current
            if depth == max_depth:
                continue
            if isinstance(current, Mapping):
                for child in reversed(list(current.values())):
                    stack.append((child, depth + 1))
            elif isinstance(current, (list, tuple)):
                for child in reversed(current):
                    stack.append((child, depth + 1))

    @staticmethod
    def _normalize(name: str) -> str:
        return name.replace("_", "").lower()

    @classmethod
    def _looks_like_direct_object(cls, mapping: Mapping[str, Any], group: str) -> bool:
        normalized = {cls._normalize(str(key)) for key in mapping}
        required = {cls._normalize(key) for key in cls._DIRECT_FIELD_GROUPS[group]}
        return bool(normalized & required)

    @classmethod
    def _matching_value(cls, mapping: Mapping[str, Any], key_names: tuple[str, ...]) -> Any:
        normalized = {cls._normalize(str(key)): key for key in mapping}
        for name in key_names:
            for candidate in (name, name.replace("_", "")):
                if candidate in mapping:
                    return mapping[candidate]
            actual = normalized.get(cls._normalize(name))
            if actual is not None:
                return mapping[actual]
        return None

    @classmethod
    def _groups_for_keys(cls, keys: tuple[str, ...]) -> tuple[str, ...]:
        normalized = {cls._normalize(key) for key in keys}
        aliases = {
            "fundamentals": "fundamentals",
            "statistics": "fundamentals",
            "riskrates": "risk_rates",
            "instrumentriskrates": "risk_rates",
            "events": "reports",
            "reports": "reports",
            "insiderdeals": "insiders",
            "insiders": "insiders",
            "items": "news",
            "news": "news",
            "signals": "signals",
            "dividends": "dividends",
            "bids": "microstructure",
            "asks": "microstructure",
        }
        groups: list[str] = []
        for name, group in aliases.items():
            if name in normalized and group not in groups:
                groups.append(group)
        return tuple(groups)

    @classmethod
    def _first(cls, payload: Any, *keys: str) -> Any:
        groups = cls._groups_for_keys(tuple(keys))
        # Find a concrete contract record before considering an envelope.
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for group in groups:
                if cls._looks_like_direct_object(current, group):
                    return current

        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            value = cls._matching_value(current, tuple(keys))
            if value is None:
                continue
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, Mapping):
                        for group in groups:
                            if cls._looks_like_direct_object(item, group):
                                return item
                if value:
                    return value[0]
            elif isinstance(value, Mapping):
                for nested in cls._walk(value, max_depth=8):
                    if isinstance(nested, Mapping) and any(
                        cls._looks_like_direct_object(nested, group) for group in groups
                    ):
                        return nested
                if not groups:
                    return value
            else:
                return value
        return None

    @classmethod
    def _extract_list(cls, value: Any, *, max_depth: int = 8) -> list[Any]:
        if isinstance(value, list):
            return value
        if not isinstance(value, Mapping):
            return []
        stack: list[tuple[Any, int]] = [(value, 0)]
        seen: set[int] = set()
        while stack:
            current, depth = stack.pop()
            if depth > max_depth or current is None:
                continue
            if isinstance(current, (Mapping, list, tuple)):
                identity = id(current)
                if identity in seen:
                    continue
                seen.add(identity)
            if isinstance(current, list):
                return current
            if isinstance(current, Mapping):
                for child in reversed(list(current.values())):
                    stack.append((child, depth + 1))
        return []

    @classmethod
    def _many(cls, payload: Any, *keys: str) -> list[Any]:
        if isinstance(payload, list):
            return payload
        target_names = {cls._normalize(name) for name in keys}
        groups = cls._groups_for_keys(tuple(keys))

        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) not in target_names:
                    continue
                extracted = cls._extract_list(value)
                if extracted:
                    return extracted
                if isinstance(value, Mapping) and groups and any(
                    cls._looks_like_direct_object(value, group) for group in groups
                ):
                    return [value]

        if groups:
            for current in cls._walk(payload):
                if not isinstance(current, (list, tuple)) or not current:
                    continue
                mappings = [item for item in current if isinstance(item, Mapping)]
                if mappings and any(
                    cls._looks_like_direct_object(item, group)
                    for item in mappings
                    for group in groups
                ):
                    return list(current)
            if isinstance(payload, Mapping) and any(
                cls._looks_like_direct_object(payload, group) for group in groups
            ):
                return [payload]
        return []

    def collect(self, instrument_uid: str):
        result = super().collect(instrument_uid)
        failed = set(result.failed_sources)
        fetched = set(result.fetched_sources)

        if "fundamentals" in fetched and "fundamentals_mapping" in failed:
            raw = self.client.get_asset_fundamentals(instrument_uid)
            candidate = self._first(raw, "fundamentals", "statistics")
            mapped = map_fundamentals(candidate)
            if mapped is not None:
                failed.discard("fundamentals_mapping")
                result = replace(result, fundamentals=mapped)

        if "insiders" in fetched and "insiders_mapping" in failed:
            raw = self.client.get_insider_deals(instrument_uid, 100)
            items = self._many(raw, "insider_deals", "insiders")
            if items:
                failed.discard("insiders_mapping")
                result = replace(result, insider_transactions=tuple(map_insider(item) for item in items))

        if "reports" in fetched and "reports_mapping" in failed:
            raw = self.client.get_asset_reports(instrument_uid, None, None)
            items = self._many(raw, "events", "reports")
            if items:
                failed.discard("reports_mapping")
                result = replace(result, reports=tuple(self._map_report(item) for item in items))

        if "risk_rates" in fetched and "risk_rates_mapping" in failed:
            raw_risk = self.client.get_risk_rates([instrument_uid])
            risk_items = self._many(raw_risk, "risk_rates", "instrument_risk_rates", "items")
            mapped_risk = map_risk_rates({"risk_rates": risk_items}) if risk_items else None
            if mapped_risk is not None:
                failed.discard("risk_rates_mapping")
                result = replace(result, risk_data=mapped_risk)

        if "order_book" in fetched and result.order_book is None:
            raw_book = self.client.get_order_book(instrument_uid, 10)
            bids = self._many(raw_book, "bids")
            asks = self._many(raw_book, "asks")
            mapped_book = map_order_book({"bids": bids, "asks": asks}) if bids or asks else None
            if mapped_book is not None:
                result = replace(result, order_book=mapped_book)

        result = replace(result, failed_sources=tuple(sorted(failed)))
        return result


__all__ = ["RobustContractAnalysisDataServiceV081"]
