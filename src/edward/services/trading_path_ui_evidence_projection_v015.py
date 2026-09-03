from __future__ import annotations

from dataclasses import dataclass
from typing import Any


UI_EVIDENCE_PROJECTION_VERSION_V015 = "0.8.15"


@dataclass(frozen=True, slots=True)
class TradingPathUIEvidenceProjectionV015:
    """Read-only projection of canonical v0.8.15 evidence for UI rendering."""

    statistical_gate: bool | None
    wf_persistence_pct: float | None
    wf_worst_window_excess_pct: float | None
    oos_excess_pct: float | None
    oos_worst_window_excess_pct: float | None
    regime_excess_pct: float | None
    market_excess_pct: float | None
    relative_strength_pct: float | None
    ev_pct: float | None
    ev_ci_low_pct: float | None
    ev_ci_high_pct: float | None
    ev_reliability_pct: float | None
    confidence_score: float | None
    risk_gate: bool | None
    current_state: str | None
    quality_gate_passed: bool | None
    quality_gate_reasons: tuple[str, ...]
    decision: str | None
    status: str | None
    version: str = UI_EVIDENCE_PROJECTION_VERSION_V015


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _value(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    return getattr(value, "value", value)


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


class TradingPathUIEvidenceProjectionServiceV015:
    """Project canonical analysis evidence without recomputation or decision logic."""

    @staticmethod
    def build(analysis: Any) -> TradingPathUIEvidenceProjectionV015:
        validation = _field(analysis, "validation")
        oos = _field(analysis, "independent_oos_evidence")
        market = _field(analysis, "market_context")
        ev = _field(analysis, "ev_evidence")
        quality = _field(analysis, "quality_gate")
        opportunity = _field(analysis, "opportunity")

        wf_summary = _field(analysis, "wf_summary")
        if wf_summary is None:
            wf_summary = _field(validation, "wf_summary")

        reasons = _field(quality, "reasons", ())
        if reasons is None:
            reasons = ()

        return TradingPathUIEvidenceProjectionV015(
            statistical_gate=(
                _field(validation, "statistical_valid") is True
                and _field(validation, "overlap_valid") is True
                and _field(validation, "multiple_testing_valid") is True
            ) if validation is not None else None,
            wf_persistence_pct=_float_or_none(
                _field(wf_summary, "persistence_pct", _field(validation, "wf_persistence_pct"))
            ),
            wf_worst_window_excess_pct=_float_or_none(
                _field(wf_summary, "worst_window_excess_pct")
            ),
            oos_excess_pct=_float_or_none(_field(oos, "excess_return_pct")),
            oos_worst_window_excess_pct=_float_or_none(_field(oos, "worst_window_excess_pct")),
            regime_excess_pct=_float_or_none(_field(market, "regime_excess_pct")),
            market_excess_pct=_float_or_none(_field(market, "market_excess_pct")),
            relative_strength_pct=_float_or_none(_field(market, "relative_strength_pct")),
            ev_pct=_float_or_none(
                _field(ev, "expected_value_pct", _field(opportunity, "expected_value_pct"))
            ),
            ev_ci_low_pct=_float_or_none(_field(ev, "ev_ci_low_pct")),
            ev_ci_high_pct=_float_or_none(_field(ev, "ev_ci_high_pct")),
            ev_reliability_pct=_float_or_none(_field(ev, "edge_reliability_pct")),
            confidence_score=_float_or_none(
                _field(ev, "confidence_score", _field(opportunity, "confidence"))
            ),
            risk_gate=_field(quality, "risk_gate"),
            current_state=_value(_field(analysis, "current_state")),
            quality_gate_passed=_field(quality, "passed"),
            quality_gate_reasons=tuple(str(reason) for reason in reasons),
            decision=_value(_field(analysis, "decision")),
            status=_value(_field(analysis, "status")),
        )


__all__ = [
    "UI_EVIDENCE_PROJECTION_VERSION_V015",
    "TradingPathUIEvidenceProjectionV015",
    "TradingPathUIEvidenceProjectionServiceV015",
]
