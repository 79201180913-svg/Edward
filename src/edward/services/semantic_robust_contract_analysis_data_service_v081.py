from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import logging
from typing import Any

from edward.services.contract_evidence_mapper_v081 import map_risk_rates
from edward.services.robust_contract_analysis_data_service_v081 import RobustContractAnalysisDataServiceV081


logger = logging.getLogger(__name__)


class SemanticRobustContractAnalysisDataServiceV081(RobustContractAnalysisDataServiceV081):
    """Classify valid empty/error contract results as unavailable, not mapping errors."""

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

    @classmethod
    def _find_collections(cls, payload: Any, *keys: str) -> list[tuple[str, int, str]]:
        normalized_keys = {cls._normalize(key) for key in keys}
        found: list[tuple[str, int, str]] = []
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) not in normalized_keys:
                    continue
                if isinstance(value, (list, tuple)):
                    found.append((str(raw_key), len(value), type(value).__name__))
                else:
                    found.append((str(raw_key), -1, type(value).__name__))
        return found

    @classmethod
    def _risk_debug_summary(cls, payload: Any) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "root_type": type(payload).__name__,
            "root_keys": list(payload.keys()) if isinstance(payload, Mapping) else None,
            "collections": cls._find_collections(payload, "instrument_risk_rates", "risk_rates", "items"),
            "error_items": [],
            "direct_numeric_items": [],
            "contract_rate_array_items": [],
        }
        normalized_keys = {
            cls._normalize("instrument_risk_rates"),
            cls._normalize("risk_rates"),
            cls._normalize("items"),
        }
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) not in normalized_keys or not isinstance(value, (list, tuple)):
                    continue
                for index, item in enumerate(value):
                    if not isinstance(item, Mapping):
                        summary["error_items"].append({"index": index, "item_type": type(item).__name__})
                        continue
                    long_rates = item.get("long_risk_rates")
                    short_rates = item.get("short_risk_rates")
                    error = item.get("error", item.get("Error"))
                    entry = {
                        "index": index,
                        "keys": list(item.keys()),
                        "instrument_uid": item.get("instrument_uid"),
                        "error": None if error is None else str(error),
                        "long_risk_rates_type": type(long_rates).__name__,
                        "long_risk_rates_len": len(long_rates) if isinstance(long_rates, (list, tuple)) else None,
                        "short_risk_rates_type": type(short_rates).__name__,
                        "short_risk_rates_len": len(short_rates) if isinstance(short_rates, (list, tuple)) else None,
                    }
                    if entry["error"]:
                        summary["error_items"].append(entry)
                    if (isinstance(long_rates, (list, tuple)) or isinstance(short_rates, (list, tuple))):
                        summary["contract_rate_array_items"].append(entry)
                    if any(item.get(key) is not None for key in ("long_risk_rate", "short_risk_rate", "dlong", "dshort", "dlong_client", "dshort_client")):
                        summary["direct_numeric_items"].append(entry)
        return summary

    @classmethod
    def _has_contract_error(cls, payload: Any, *keys: str) -> bool:
        normalized_keys = {cls._normalize(key) for key in keys}
        for current in cls._walk(payload):
            if not isinstance(current, Mapping):
                continue
            for raw_key, value in current.items():
                if cls._normalize(str(raw_key)) not in normalized_keys or not isinstance(value, (list, tuple)):
                    continue
                for item in value:
                    if not isinstance(item, Mapping):
                        continue
                    error = item.get("error")
                    if error is None:
                        error = item.get("Error")
                    if error is not None and str(error).strip():
                        return True
        return False

    @classmethod
    def _has_empty_risk_rate_arrays(cls, payload: Any) -> bool:
        """True when a valid RiskRateResult exposes rate arrays and all are empty."""
        normalized_keys = {
            cls._normalize("instrument_risk_rates"),
            cls._normalize("risk_rates"),
            cls._normalize("items"),
        }
        found_result = False
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
                        found_result = True
                        long_empty = not isinstance(long_rates, (list, tuple)) or len(long_rates) == 0
                        short_empty = not isinstance(short_rates, (list, tuple)) or len(short_rates) == 0
                        if long_empty and short_empty:
                            return True
        return False if found_result else False

    def collect(self, instrument_uid: str):
        logger.warning("[V081 SEMANTIC START] instrument_uid=%s client=%s", instrument_uid, type(self.client).__name__)
        result = super().collect(instrument_uid)
        failed = set(result.failed_sources)
        unavailable = set()

        logger.warning(
            "[V081 SEMANTIC AFTER SUPER] instrument_uid=%s failed=%s fetched=%s risk_data=%r",
            instrument_uid,
            sorted(failed),
            sorted(getattr(result, "fetched_sources", ()) or ()),
            result.risk_data,
        )

        checks = (
            ("fundamentals_mapping", ("fundamentals", "statistics"), "fundamentals"),
            ("insiders_mapping", ("insider_deals", "insiders"), "insiders"),
            ("reports_mapping", ("events", "reports"), "reports"),
            ("risk_rates_mapping", ("instrument_risk_rates", "risk_rates", "items"), "risk_rates"),
        )
        for failure_name, keys, source_name in checks:
            if failure_name not in failed:
                continue

            logger.warning("[V081 SEMANTIC RETRY] failure=%s source=%s keys=%s", failure_name, source_name, keys)
            try:
                if source_name == "fundamentals":
                    raw = self.client.get_asset_fundamentals(instrument_uid)
                elif source_name == "insiders":
                    raw = self.client.get_insider_deals(instrument_uid, 100)
                elif source_name == "reports":
                    raw = self.client.get_asset_reports(instrument_uid, None, None)
                else:
                    raw = self.client.get_risk_rates([instrument_uid])
            except Exception as exc:
                logger.exception("[V081 SEMANTIC RETRY ERROR] source=%s exc=%r", source_name, exc)
                continue

            if source_name == "risk_rates":
                logger.warning("[V081 RISK RAW] instrument_uid=%s summary=%r", instrument_uid, self._risk_debug_summary(raw))
                risk_items = self._many(raw, *keys)
                logger.warning("[V081 RISK MAP INPUT] instrument_uid=%s item_count=%d items=%r", instrument_uid, len(risk_items), risk_items)
                mapped_risk = map_risk_rates({"risk_rates": risk_items}) if risk_items else None
                logger.warning(
                    "[V081 RISK MAP RESULT] instrument_uid=%s mapped=%r mapped_type=%s",
                    instrument_uid,
                    mapped_risk,
                    type(mapped_risk).__name__ if mapped_risk is not None else "None",
                )
                if mapped_risk is not None:
                    failed.discard(failure_name)
                    result = replace(result, risk_data=mapped_risk)
                    logger.warning(
                        "[V081 SEMANTIC -> MAPPED] source=%s removed_failure=%s risk_data=%r",
                        source_name,
                        failure_name,
                        mapped_risk,
                    )
                    continue

                if self._has_empty_risk_rate_arrays(raw) or self._has_contract_error(raw, *keys):
                    failed.discard(failure_name)
                    unavailable.add(source_name)
                    logger.warning(
                        "[V081 SEMANTIC -> RISK UNAVAILABLE] source=%s reason=EMPTY_OR_ERROR_RATE_RESULT",
                        source_name,
                    )
                    continue

            empty = self._has_empty_collection(raw, *keys)
            nonempty = self._has_nonempty_collection(raw, *keys)
            contract_error = self._has_contract_error(raw, *keys)

            logger.warning(
                "[V081 SEMANTIC CLASSIFY] source=%s empty=%s nonempty=%s contract_error=%s raw_type=%s",
                source_name,
                empty,
                nonempty,
                contract_error,
                type(raw).__name__,
            )

            if empty or contract_error:
                failed.discard(failure_name)
                unavailable.add(source_name)
                logger.warning("[V081 SEMANTIC -> UNAVAILABLE] source=%s removed_failure=%s", source_name, failure_name)
            elif not nonempty and isinstance(raw, (Mapping, list, tuple)) and not raw:
                failed.discard(failure_name)
                unavailable.add(source_name)
                logger.warning("[V081 SEMANTIC -> EMPTY UNAVAILABLE] source=%s removed_failure=%s", source_name, failure_name)
            else:
                logger.warning("[V081 SEMANTIC KEEP FAILURE] source=%s failure=%s", source_name, failure_name)

        diagnostics = list(getattr(result, "unavailable_sources", ()) or ())
        diagnostics.extend(sorted(unavailable))
        deduped = tuple(dict.fromkeys(diagnostics))
        if hasattr(result, "unavailable_sources"):
            result = replace(result, unavailable_sources=deduped)
        result = replace(result, failed_sources=tuple(sorted(failed)))

        logger.warning(
            "[V081 SEMANTIC FINAL] instrument_uid=%s failed=%s unavailable=%s risk_data=%r",
            instrument_uid,
            result.failed_sources,
            getattr(result, "unavailable_sources", ()),
            result.risk_data,
        )
        return result


__all__ = ["SemanticRobustContractAnalysisDataServiceV081"]
