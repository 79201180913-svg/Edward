from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Mapping, Sequence


PORTFOLIO_IMPACT_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class PortfolioImpactResult:
    portfolio_risk_before_pct: float
    portfolio_risk_after_pct: float
    marginal_risk_pct: float
    correlation_to_portfolio: float
    diversification_benefit_pct: float
    expected_return_before_pct: float
    expected_return_after_pct: float
    expected_return_impact_pct: float
    concentration_penalty_pct: float
    portfolio_impact_score: float
    version: str = PORTFOLIO_IMPACT_VERSION


class PortfolioImpactService:
    """Estimate the marginal effect of a candidate asset on a portfolio."""

    @staticmethod
    def _portfolio_returns(weights: Mapping[str, float], asset_returns: Mapping[str, Sequence[float]]) -> list[float]:
        length = min((len(values) for values in asset_returns.values()), default=0)
        result: list[float] = []
        for index in range(length):
            result.append(sum(float(weights.get(asset, 0.0)) * float(values[index]) for asset, values in asset_returns.items()))
        return result

    @staticmethod
    def _correlation(left: Sequence[float], right: Sequence[float]) -> float:
        n = min(len(left), len(right))
        if n < 2:
            return 0.0
        left = list(left[:n])
        right = list(right[:n])
        left_mean = mean(left)
        right_mean = mean(right)
        numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
        left_var = sum((a - left_mean) ** 2 for a in left)
        right_var = sum((b - right_mean) ** 2 for b in right)
        denominator = sqrt(left_var * right_var)
        return numerator / denominator if denominator else 0.0

    @staticmethod
    def _risk(returns: Sequence[float]) -> float:
        return pstdev(returns) * 100.0 if len(returns) > 1 else 0.0

    @classmethod
    def calculate(
        cls,
        *,
        weights: Mapping[str, float],
        asset_returns: Mapping[str, Sequence[float]],
        candidate_id: str,
        candidate_weight: float,
        candidate_expected_return_pct: float,
        concentration_penalty_pct: float = 0.0,
    ) -> PortfolioImpactResult:
        if candidate_weight < 0:
            raise ValueError("candidate_weight cannot be negative")
        current = cls._portfolio_returns(weights, asset_returns)
        current_risk = cls._risk(current)
        current_expected = mean(current) * 100.0 if current else 0.0

        candidate = list(asset_returns.get(candidate_id, ()))
        if not candidate:
            return PortfolioImpactResult(current_risk, current_risk, 0.0, 0.0, 0.0, current_expected, current_expected, 0.0, max(0.0, concentration_penalty_pct), 0.0)
        n = min(len(current), len(candidate))
        current = current[-n:] if n else []
        candidate = candidate[-n:] if n else []
        corr = cls._correlation(current, candidate) if current else 0.0

        new_weights = dict(weights)
        new_weights[candidate_id] = float(new_weights.get(candidate_id, 0.0)) + candidate_weight
        total_weight = sum(max(0.0, float(value)) for value in new_weights.values())
        if total_weight > 0:
            new_weights = {key: max(0.0, float(value)) / total_weight for key, value in new_weights.items()}
        augmented = dict(asset_returns)
        augmented[candidate_id] = candidate
        after = cls._portfolio_returns(new_weights, augmented)
        after_risk = cls._risk(after)
        after_expected = mean(after) * 100.0 if after else current_expected
        marginal = after_risk - current_risk
        benefit = max(0.0, current_risk - after_risk)
        expected_impact = after_expected - current_expected
        raw_score = 50.0 + benefit * 10.0 + expected_impact * 2.0 - max(0.0, marginal) * 10.0 - max(0.0, concentration_penalty_pct)
        score = max(0.0, min(100.0, raw_score))
        return PortfolioImpactResult(current_risk, after_risk, marginal, corr, benefit, current_expected, after_expected, expected_impact, max(0.0, concentration_penalty_pct), score)


__all__ = ["PORTFOLIO_IMPACT_VERSION", "PortfolioImpactResult", "PortfolioImpactService"]
