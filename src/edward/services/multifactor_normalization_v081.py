from __future__ import annotations

from dataclasses import replace

from edward.services.multifactor_analysis_service_v081 import Evidence, MultiFactorResult, MultiFactorAnalysisServiceV081


def normalize(result: MultiFactorResult, *, portfolio_context_available: bool, session_available: bool) -> MultiFactorResult:
    portfolio = result.portfolio
    session = result.session
    if not portfolio_context_available and portfolio.evidence.available:
        portfolio = replace(
            portfolio,
            evidence=Evidence(
                "portfolio", "UNAVAILABLE", 0.0, 0.0,
                available=False,
                reason="NO_PORTFOLIO_CONTEXT",
            ),
        )
    if not session_available and session.evidence.available:
        session = replace(
            session,
            session="UNKNOWN",
            quality_score=0.0,
            is_execution_allowed=False,
            evidence=Evidence(
                "session", "UNAVAILABLE", 0.0, 0.0,
                available=False,
                reason="NO_SESSION_CONTEXT",
            ),
        )

    evidence = [
        result.fundamentals.evidence,
        result.microstructure.evidence,
        result.volume_pressure.evidence,
        result.signals.evidence,
        result.event_risk.evidence,
        result.dividends.evidence,
        result.insider.evidence,
        session.evidence,
        result.instrument_risk.evidence,
        portfolio.evidence,
    ]
    available = [item for item in evidence if item.available]
    if not available:
        aggregate_score = aggregate_reliability = conflict = 0.0
    else:
        aggregate_score = sum(item.quality for item in available) / len(available)
        aggregate_reliability = sum(item.reliability for item in available) / len(available)
        positives = sum(item.direction == "POSITIVE" for item in available)
        negatives = sum(item.direction == "NEGATIVE" for item in available)
        conflict = min(30.0, min(positives, negatives) * 3.0)

    return replace(
        result,
        portfolio=portfolio,
        session=session,
        aggregate_evidence_score=aggregate_score,
        aggregate_reliability_score=aggregate_reliability,
        conflict_penalty=conflict,
    )


__all__ = ["normalize"]
