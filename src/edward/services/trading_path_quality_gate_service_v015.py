from __future__ import annotations

from dataclasses import dataclass


QUALITY_GATE_VERSION_V015 = "0.8.15"


@dataclass(frozen=True, slots=True)
class TradingPathQualityGateResultV015:
    """Explicit evidence gate; every critical gate must pass independently."""

    statistical_gate: bool
    wf_gate: bool
    oos_gate: bool
    ev_gate: bool
    market_context_gate: bool
    risk_gate: bool
    current_state_gate: bool
    passed: bool
    reasons: tuple[str, ...]
    version: str = QUALITY_GATE_VERSION_V015


class TradingPathQualityGateServiceV015:
    """Apply the v0.8.15 hard quality gate without weighted compensation."""

    @staticmethod
    def evaluate(
        *,
        validation: object,
        wf_summary: object | None,
        independent_oos_evidence: object,
        market_context: object,
        risk_gate: bool | None,
        current_state: object,
        ev_evidence: object | None = None,
    ) -> TradingPathQualityGateResultV015:
        reasons: list[str] = []
        statistical_gate = (
            getattr(validation, "statistical_valid", False) is True
            and getattr(validation, "overlap_valid", False) is True
            and getattr(validation, "multiple_testing_valid", False) is True
        )
        if not statistical_gate:
            reasons.append("STATISTICAL_GATE_FAILED")
        wf_gate = wf_summary is not None and getattr(wf_summary, "passed", False) is True
        if not wf_gate:
            reasons.append("WF_GATE_FAILED")
        oos_gate = (
            getattr(independent_oos_evidence, "status", None) == "READY"
            and getattr(independent_oos_evidence, "parameters_locked", False) is True
            and getattr(independent_oos_evidence, "excess_return_pct", None) is not None
            and getattr(independent_oos_evidence, "excess_return_pct", 0.0) > 0.0
            and getattr(independent_oos_evidence, "worst_window_excess_pct", None) is not None
            and getattr(independent_oos_evidence, "worst_window_excess_pct", 0.0) > 0.0
        )
        if not oos_gate:
            reasons.append("OOS_GATE_FAILED")
        if ev_evidence is None:
            ev_gate = True
        else:
            ev_gate = (
                getattr(ev_evidence, "status", None) == "READY"
                and getattr(ev_evidence, "positive_ev", False) is True
                and getattr(ev_evidence, "statistically_positive_ev", False) is True
            )
        if not ev_gate:
            reasons.append("EV_GATE_FAILED")
        market_context_gate = (
            getattr(market_context, "context_status", None) == "FULL"
            and getattr(market_context, "regime_excess_pct", None) is not None
            and getattr(market_context, "regime_excess_pct", 0.0) > 0.0
            and getattr(market_context, "market_excess_pct", None) is not None
            and getattr(market_context, "market_excess_pct", 0.0) > 0.0
        )
        if not market_context_gate:
            reasons.append("MARKET_CONTEXT_GATE_FAILED")
        risk_gate_result = risk_gate is True
        if not risk_gate_result:
            reasons.append("RISK_GATE_FAILED")
        current_state_gate = getattr(current_state, "value", current_state) == "entry_ready"
        if not current_state_gate:
            reasons.append("CURRENT_STATE_GATE_FAILED")
        return TradingPathQualityGateResultV015(
            statistical_gate=statistical_gate,
            wf_gate=wf_gate,
            oos_gate=oos_gate,
            ev_gate=ev_gate,
            market_context_gate=market_context_gate,
            risk_gate=risk_gate_result,
            current_state_gate=current_state_gate,
            passed=all((statistical_gate, wf_gate, oos_gate, ev_gate, market_context_gate, risk_gate_result, current_state_gate)),
            reasons=tuple(reasons),
        )


__all__ = [
    "QUALITY_GATE_VERSION_V015",
    "TradingPathQualityGateResultV015",
    "TradingPathQualityGateServiceV015",
]
