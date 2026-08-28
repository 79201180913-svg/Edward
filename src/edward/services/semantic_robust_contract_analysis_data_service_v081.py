from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from edward.services.robust_contract_analysis_data_service_v081 import RobustContractAnalysisDataServiceV081


class SemanticRobustContractAnalysisDataServiceV081(RobustContractAnalysisDataServiceV081):
    """Classify valid empty contract collections as unavailable, not mapping errors."""

    _DIRECT_FIELD_GROUPS = {
        **RobustContractAnalysisDataServiceV081._DIRECT_FIELD_GROUPS,
        "microstructure": {"bids", "asks", "price", "quantity"},
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

    @classmethod
    def _has_empty_collection(cls, payload: Any, *keys: str) -> bool:
        normalized_keys = {cls._normalize(key) for key in keys}
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) in normalized_keys and isinstance(value, (list, tuple)):
                    return len(value) == 0
        return False

    @classmethod
    def _has_nonempty_collection(cls, payload: Any, *keys: str) -> bool:
        normalized_keys = {cls._normalize(key) for key in keys}
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) in normalized_keys and isinstance(value, (list, tuple)):
                    return len(value) > 0
        return False

    def collect(self, instrument_uid: str):
        result = super().collect(instrument_uid)
        failed = set(result.failed_sources)
        unavailable = set()

        checks = (
            ("fundamentals_mapping", ("fundamentals", "statistics"), "fundamentals"),
            ("insiders_mapping", ("insider_deals", "insiders"), "insiders"),
            ("reports_mapping", ("events", "reports"), "reports"),
            ("risk_rates_mapping", ("instrument_risk_rates", "risk_rates", "items"), "risk_rates"),
        )
        for failure_name, keys, source_name in checks:
            if failure_name not in failed:
                continue
            try:
                if source_name == "fundamentals":
                    raw = self.client.get_asset_fundamentals(instrument_uid)
                elif source_name == "insiders":
                    raw = self.client.get_insider_deals(instrument_uid, 100)
                elif source_name == "reports":
                    raw = self.client.get_asset_reports(instrument_uid, None, None)
                else:
                    raw = self.client.get_risk_rates([instrument_uid])
            except Exception:
                continue
            if self._has_empty_collection(raw, *keys):
                failed.discard(failure_name)
                unavailable.add(source_name)
            elif not self._has_nonempty_collection(raw, *keys) and isinstance(raw, (Mapping, list, tuple)) and not raw:
                failed.discard(failure_name)
                unavailable.add(source_name)

        diagnostics = list(getattr(result, "unavailable_sources", ()) or ())
        diagnostics.extend(sorted(unavailable))
        deduped = tuple(dict.fromkeys(diagnostics))

        if hasattr(result, "unavailable_sources"):
            result = result.__class__(**{**result.__dict__, "unavailable_sources": deduped}) if hasattr(result, "__dict__") else result
        result = result.__class__(**{**result.__dict__, "failed_sources": tuple(sorted(failed))}) if hasattr(result, "__dict__") else result
        return result


__all__ = ["SemanticRobustContractAnalysisDataServiceV081"]
