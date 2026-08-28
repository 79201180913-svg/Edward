from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from edward.services.contract_analysis_data_service_v081 import ContractAnalysisDataServiceV081
from edward.services.contract_evidence_mapper_v081 import map_order_book, map_risk_rates


class RobustContractAnalysisDataServiceV081(ContractAnalysisDataServiceV081):
    """v0.8.1 collector with recursive contract-response unwrapping."""

    _ENVELOPE_KEYS = {
        "data",
        "response",
        "result",
        "payload",
        "body",
        "content",
        "value",
    }

    @classmethod
    def _walk(cls, value: Any, *, max_depth: int = 8):
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
    def _matching_value(cls, mapping: Mapping[str, Any], key_names: tuple[str, ...]) -> Any:
        normalized = {cls._normalize(str(key)): key for key in mapping}
        for name in key_names:
            direct_names = (name, name.replace("_", ""))
            for candidate in direct_names:
                if candidate in mapping:
                    return mapping[candidate]
            actual = normalized.get(cls._normalize(name))
            if actual is not None:
                return mapping[actual]
        return None

    @classmethod
    def _first(cls, payload: Any, *keys: str) -> Any:
        for current in cls._walk(payload):
            if isinstance(current, Mapping):
                value = cls._matching_value(current, keys)
                if value is not None:
                    if isinstance(value, list):
                        return value[0] if value else None
                    return value
        return None

    @classmethod
    def _many(cls, payload: Any, *keys: str) -> list[Any]:
        if isinstance(payload, list):
            return payload
        target_names = {cls._normalize(name) for name in keys}
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) in target_names and isinstance(value, list):
                    return value
        return []

    def collect(self, instrument_uid: str):
        result = super().collect(instrument_uid)
        failed = set(result.failed_sources)
        fetched = set(result.fetched_sources)

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
