from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt
from statistics import mean, pstdev
from typing import Sequence

from edward.services.research_backtest_service_v08 import BacktestTrade


EXPECTED_VALUE_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class ExpectedValueResult:
    probability_profit_pct: float
    probability_loss_pct: float
    average_win_pct: float
    average_loss_pct: float
    expected_return_pct: float
    expected_loss_pct: float
    expected_value_pct: float
    risk_adjusted_ev: float
    p10_pct: float
    p25_pct: float
    median_pct: float
    p75_pct: float
    p90_pct: float
    uncertainty_width_pct: float
    observations: int
    confidence: str
    available: bool = True
    unavailable_reason: str | None = None
    ev_ci_low_pct: float | None = None
    ev_ci_high_pct: float | None = None
    edge_reliability_pct: float | None = None
    edge_reliability_level: str = "LOW"
    version: str = EXPECTED_VALUE_VERSION


class ExpectedValueEngine:
    """Estimate after-cost expected trade value from realized historical outcomes."""

    @staticmethod
    def _percentile(values: Sequence[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * percentile / 100.0
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

    @staticmethod
    def _t_critical_95(df: int) -> float:
        table = {
            1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
            6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
            11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
            16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
            21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
            26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
        }
        return table.get(max(1, df), 1.96)

    @staticmethod
    def _normal_cdf(value: float) -> float:
        return 0.5 * (1.0 + erf(value / sqrt(2.0)))

    @classmethod
    def _ev_reliability(cls, outcomes: Sequence[float], expected_value: float) -> tuple[float, float, float, str]:
        observations = len(outcomes)
        if observations < 2:
            return 0.0, None if observations == 0 else expected_value, None if observations == 0 else expected_value, "LOW"
        sample_std = pstdev(outcomes)
        if sample_std == 0.0:
            low = high = expected_value
            reliability = 100.0 if expected_value > 0 else 0.0 if expected_value < 0 else 50.0
        else:
            standard_error = sample_std / sqrt(observations)
            critical = cls._t_critical_95(observations - 1)
            half_width = critical * standard_error
            low = expected_value - half_width
            high = expected_value + half_width
            z = expected_value / standard_error
            reliability = cls._normal_cdf(z) * 100.0
        level = "HIGH" if observations >= 100 and reliability >= 95.0 and low > 0 else "MEDIUM" if observations >= 30 and reliability >= 75.0 and low > 0 else "LOW"
        return reliability, low, high, level

    @classmethod
    def from_trades(cls, trades: Sequence[BacktestTrade]) -> ExpectedValueResult:
        outcomes = [float(trade.net_return_pct) for trade in trades]
        if not outcomes:
            return ExpectedValueResult(
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0,
                "Low", False, "NO_REALIZED_OUTCOMES",
                None, None, 0.0, "LOW",
            )

        wins = [value for value in outcomes if value > 0]
        losses = [value for value in outcomes if value < 0]
        p_win = len(wins) / len(outcomes)
        p_loss = len(losses) / len(outcomes)
        avg_win = mean(wins) if wins else 0.0
        avg_loss = abs(mean(losses)) if losses else 0.0
        expected_return = p_win * avg_win
        expected_loss = p_loss * avg_loss
        expected_value = expected_return - expected_loss
        dispersion = pstdev(outcomes) if len(outcomes) > 1 else 0.0
        risk_adjusted = expected_value / dispersion if dispersion > 0 else (expected_value if expected_value > 0 else 0.0)
        observations = len(outcomes)
        confidence = "High" if observations >= 100 else "Medium" if observations >= 30 else "Low"
        edge_reliability, ev_ci_low, ev_ci_high, edge_level = cls._ev_reliability(outcomes, expected_value)

        p10 = cls._percentile(outcomes, 10)
        p25 = cls._percentile(outcomes, 25)
        median = cls._percentile(outcomes, 50)
        p75 = cls._percentile(outcomes, 75)
        p90 = cls._percentile(outcomes, 90)
        return ExpectedValueResult(
            probability_profit_pct=p_win * 100.0,
            probability_loss_pct=p_loss * 100.0,
            average_win_pct=avg_win,
            average_loss_pct=avg_loss,
            expected_return_pct=expected_return,
            expected_loss_pct=expected_loss,
            expected_value_pct=expected_value,
            risk_adjusted_ev=risk_adjusted,
            p10_pct=p10,
            p25_pct=p25,
            median_pct=median,
            p75_pct=p75,
            p90_pct=p90,
            uncertainty_width_pct=p90 - p10,
            observations=observations,
            confidence=confidence,
            ev_ci_low_pct=ev_ci_low,
            ev_ci_high_pct=ev_ci_high,
            edge_reliability_pct=edge_reliability,
            edge_reliability_level=edge_level,
        )

    @classmethod
    def from_returns(cls, returns_pct: Sequence[float]) -> ExpectedValueResult:
        synthetic = tuple(
            BacktestTrade(None, None, 0.0, 0.0, float(value), 0.0, float(value))
            for value in returns_pct
        )
        return cls.from_trades(synthetic)


__all__ = ["EXPECTED_VALUE_VERSION", "ExpectedValueResult", "ExpectedValueEngine"]
