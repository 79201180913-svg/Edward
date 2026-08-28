from __future__ import annotations

from typing import Any, Mapping


def _value(data: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(data, Mapping) and name in data:
            return data[name]
        if hasattr(data, name):
            return getattr(data, name)
    return default


def emit_multifactor_diagnostics(*, instrument_uid: str, data: Any, result: Any) -> None:
    """Emit a compact end-to-end trace for one v0.8.1 analysis run."""
    risk_data = getattr(data, "risk_data", None)
    factor = result.multifactor.instrument_risk
    evidence = factor.evidence

    raw_dlong = _value(risk_data, "dlong", "dlong_client")
    raw_dshort = _value(risk_data, "dshort", "dshort_client")
    raw_short_enabled = _value(risk_data, "short_enabled", "short_enabled_flag")

    print(
        "[V081 MULTIFACTOR INPUT] "
        f"instrument_uid={instrument_uid} "
        f"fundamentals_available={result.multifactor.fundamentals.evidence.available} "
        f"order_book_available={result.multifactor.microstructure.evidence.available} "
        f"signals_available={result.multifactor.signals.evidence.available} "
        f"events_available={result.multifactor.event_risk.evidence.available} "
        f"insiders_available={result.multifactor.insider.evidence.available} "
        f"risk_data_type={type(risk_data).__name__} "
        f"risk_data={risk_data!r}",
        flush=True,
    )
    print(
        "[V081 RISK RAW] "
        f"dlong={raw_dlong!r} dshort={raw_dshort!r} "
        f"short_enabled={raw_short_enabled!r}",
        flush=True,
    )
    print(
        "[V081 RISK FACTOR] "
        f"long_margin_rate_pct={factor.long_margin_rate_pct!r} "
        f"short_margin_rate_pct={factor.short_margin_rate_pct!r} "
        f"short_enabled={factor.short_enabled!r} "
        f"capital_efficiency_score={factor.capital_efficiency_score!r} "
        f"risk_score={factor.risk_score!r} "
        f"direction={evidence.direction} "
        f"strength={evidence.strength!r} "
        f"reliability={evidence.reliability!r} "
        f"available={evidence.available!r} "
        f"reason={evidence.reason!r}",
        flush=True,
    )
    print(
        "[V081 FACTOR SUMMARY] "
        f"aggregate_evidence={result.multifactor.aggregate_evidence_score!r} "
        f"aggregate_reliability={result.multifactor.aggregate_reliability_score!r} "
        f"conflict={result.multifactor.conflict_penalty!r} "
        f"adjusted_opportunity={result.overlay.adjusted_opportunity_score!r} "
        f"adjusted_confidence={result.overlay.adjusted_confidence!r}",
        flush=True,
    )


__all__ = ["emit_multifactor_diagnostics"]
