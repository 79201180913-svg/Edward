from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from edward.services.contract_evidence_mapper_v081 import map_risk_rates
from edward.services.robust_contract_analysis_data_service_v081 import RobustContractAnalysisDataServiceV081


class SemanticRobustContractAnalysisDataServiceV081(RobustContractAnalysisDataServiceV081):
    """Semantic fallback/classification layer for contract-backed analysis data."""

    @staticmethod
    def _normalize(name: str) -> str:
        return str(name).replace("_", "").lower()

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

    @classmethod
    def _many(cls, payload: Any, *keys: str) -> list[Any]:
        if isinstance(payload, list):
            return payload
        targets = {cls._normalize(key) for key in keys}
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) in targets:
                    if isinstance(value, list):
                        return value
                    if isinstance(value, Mapping):
                        return [value]
        return []

    @classmethod
    def _has_empty_collection(cls, payload: Any, *keys: str) -> bool:
        targets = {cls._normalize(key) for key in keys}
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) in targets and isinstance(value, (list, tuple)):
                    return len(value) == 0
        return False

    @classmethod
    def _has_nonempty_collection(cls, payload: Any, *keys: str) -> bool:
        return bool(cls._many(payload, *keys))

    @classmethod
    def _has_contract_error(cls, payload: Any, *keys: str) -> bool:
        targets = {cls._normalize(key) for key in keys}
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) not in targets or not isinstance(value, (list, tuple)):
                    continue
                for item in value:
                    if isinstance(item, Mapping):
                        error = item.get("error", item.get("Error"))
                        if error is not None and str(error).strip():
                            return True
        return False

    @classmethod
    def _has_empty_risk_rate_arrays(cls, payload: Any) -> bool:
        normalized_keys = {cls._normalize("instrument_risk_rates"), cls._normalize("risk_rates"), cls._normalize("items")}
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) not in normalized_keys or not isinstance(value, (list, tuple)):
                    continue
                for item in value:
                    if not isinstance(item, Mapping):
                        continue
                    long_rates = item.get("long_risk_rates")
                    short_rates = item.get("short_risk_rates")
                    if isinstance(long_rates, (list, tuple)) or isinstance(short_rates, (list, tuple)):
                        long_empty = not isinstance(long_rates, (list, tuple)) or len(long_rates) == 0
                        short_empty = not isinstance(short_rates, (list, tuple)) or len(short_rates) == 0
                        if long_empty and short_empty:
                            return True
        return False

    @classmethod
    def _risk_debug_summary(cls, payload: Any) -> dict[str, Any]:
        return {
            "root_type": type(payload).__name__,
            "root_keys": list(payload.keys()) if isinstance(payload, Mapping) else None,
            "collections": [],
        }

    def collect(self, instrument_uid: str):
        result = super().collect(instrument_uid)
        failed = set(result.failed_sources)
        unavailable = set(result.unavailable_sources)

        try:
            raw_risk = self.client.get_risk_rates([instrument_uid])
        except Exception:
            raw_risk = None

        if raw_risk is not None:
            risk_items = self._many(raw_risk, "risk_rates", "instrument_risk_rates", "items")
            mapped_risk = map_risk_rates({"risk_rates": risk_items}) if risk_items else None
            if mapped_risk is not None:
                failed.discard("risk_rates_mapping")
                unavailable.discard("risk_rates_mapping")
                unavailable.discard("risk_rates")
                result = replace(result, risk_data=mapped_risk)
            elif self._has_empty_risk_rate_arrays(raw_risk) or self._has_empty_collection(raw_risk, "risk_rates", "instrument_risk_rates", "items") or self._has_contract_error(raw_risk, "risk_rates", "instrument_risk_rates", "items"):
                failed.discard("risk_rates_mapping")
                unavailable.discard("risk_rates_mapping")
                unavailable.add("risk_rates")

        result = replace(result, failed_sources=tuple(sorted(failed)), unavailable_sources=tuple(sorted(unavailable)))
        return result


__all__ = ["SemanticRobustContractAnalysisDataServiceV081"]