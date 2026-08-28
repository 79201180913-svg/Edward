from __future__ import annotations

from edward.services.confidence_service_v08 import ConfidenceService
from edward.services.uncertainty_service_v08 import UncertaintyService


def test_confidence_uses_evidence_components_and_uncertainty_penalty():
    result = ConfidenceService.calculate(
        strategy_quality=90.0,
        forecast_quality=80.0,
        regime_confidence=70.0,
        portfolio_confidence=60.0,
        uncertainty_width_pct=10.0,
    )
    assert result.version == "0.8.0"
    assert result.level in {"Low", "Medium", "High"}
    assert 0.0 <= result.overall_confidence <= 100.0
    assert result.overall_confidence < ConfidenceService.calculate(
        strategy_quality=90.0,
        forecast_quality=80.0,
        regime_confidence=70.0,
        portfolio_confidence=60.0,
        uncertainty_width_pct=0.0,
    ).overall_confidence


def test_uncertainty_exposes_distribution_percentiles():
    result = UncertaintyService.from_returns((-10.0, -2.0, 1.0, 5.0, 12.0))
    assert result.version == "0.8.0"
    assert result.observations == 5
    assert result.p10_pct <= result.p25_pct <= result.median_pct <= result.p75_pct <= result.p90_pct
    assert result.width_pct == result.p90_pct - result.p10_pct
    assert result.downside_pct <= 0.0
    assert result.upside_pct >= 0.0


def test_empty_uncertainty_is_safe():
    result = UncertaintyService.from_returns(())
    assert result.observations == 0
    assert result.width_pct == 0.0
