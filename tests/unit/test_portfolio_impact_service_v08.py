from __future__ import annotations

from edward.services.portfolio_impact_service_v08 import PortfolioImpactService


def test_candidate_with_low_correlation_can_improve_portfolio():
    result = PortfolioImpactService.calculate(
        weights={"A": 1.0},
        asset_returns={
            "A": (0.01, 0.01, -0.01, 0.01),
            "B": (-0.01, 0.01, 0.01, -0.01),
        },
        candidate_id="B",
        candidate_weight=0.5,
        candidate_expected_return_pct=5.0,
    )
    assert result.version == "0.8.0"
    assert result.correlation_to_portfolio < 0.0
    assert result.portfolio_risk_after_pct <= result.portfolio_risk_before_pct
    assert result.diversification_benefit_pct >= 0.0


def test_missing_candidate_returns_neutral_impact():
    result = PortfolioImpactService.calculate(
        weights={"A": 1.0},
        asset_returns={"A": (0.01, -0.01)},
        candidate_id="B",
        candidate_weight=0.2,
        candidate_expected_return_pct=3.0,
    )
    assert result.portfolio_risk_after_pct == result.portfolio_risk_before_pct
    assert result.portfolio_impact_score == 0.0


def test_negative_candidate_weight_is_rejected():
    try:
        PortfolioImpactService.calculate(
            weights={},
            asset_returns={"B": (0.01, 0.02)},
            candidate_id="B",
            candidate_weight=-0.1,
            candidate_expected_return_pct=3.0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Negative candidate weight must be rejected")
