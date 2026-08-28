from __future__ import annotations

from edward.services.opportunity_score_service_v08 import OpportunityScoreService


def test_high_ev_confident_setup_is_eligible():
    result = OpportunityScoreService.calculate(
        strategy_edge=90,
        forecast_edge=80,
        expected_value_score=85,
        risk_score=75,
        portfolio_impact_score=80,
        regime_compatibility=90,
        confidence=85,
    )
    assert result.version == "0.8.0"
    assert result.eligible is True
    assert result.score > 70


def test_negative_ev_cannot_produce_buy_eligible_score():
    result = OpportunityScoreService.calculate(
        strategy_edge=100,
        forecast_edge=100,
        expected_value_score=20,
        risk_score=100,
        portfolio_impact_score=100,
        regime_compatibility=100,
        confidence=100,
    )
    assert result.eligible is False
    assert result.score < 60


def test_components_are_clamped():
    result = OpportunityScoreService.calculate(
        strategy_edge=200,
        forecast_edge=-10,
        expected_value_score=70,
        risk_score=70,
        portfolio_impact_score=70,
        regime_compatibility=70,
        confidence=70,
    )
    assert result.strategy_edge == 100.0
    assert result.forecast_edge == 0.0
