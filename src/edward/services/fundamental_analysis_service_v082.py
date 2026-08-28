from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Any, Mapping

FUNDAMENTAL_ANALYSIS_VERSION = "0.8.2"


@dataclass(frozen=True, slots=True)
class FundamentalMetricResult:
    metric: str
    value: float | None
    score: float
    available: bool
    confidence: float
    freshness: float = 100.0
    direction: str = "NEUTRAL"
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FundamentalGroupResult:
    name: str
    score: float
    confidence: float
    coverage: float
    metrics: tuple[FundamentalMetricResult, ...]
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FundamentalAnalysisResult:
    business_quality: FundamentalGroupResult
    growth: FundamentalGroupResult
    cash_generation: FundamentalGroupResult
    financial_health: FundamentalGroupResult
    valuation: FundamentalGroupResult
    shareholder_return: FundamentalGroupResult
    fundamental_momentum: FundamentalGroupResult
    overall_score: float
    confidence: float
    coverage: float
    status: str
    reason_codes: tuple[str, ...] = ()
    version: str = FUNDAMENTAL_ANALYSIS_VERSION


class FundamentalAnalysisServiceV082:
    """Structured fundamental analysis over the contract-mapped v0.8.1 data.

    This service is deliberately additive. It consumes the existing mapped
    fundamentals dictionary and does not alter the v0.8.1 pipeline or contract.
    Missing metrics are unavailable evidence, not zero-valued metrics.
    """

    POSITIVE_METRICS = {
        "roe", "roic", "roa", "net_margin", "revenue_growth",
        "revenue_growth_3y", "revenue_growth_5y", "revenue_change_5y",
        "eps_growth", "ebitda_growth", "free_cash_flow",
        "free_cash_flow_to_price", "current_ratio", "dividend_yield",
        "dividend_growth", "dividend_regularity",
    }

    NEGATIVE_METRICS = {
        "net_debt_to_ebitda", "total_debt_to_ebitda",
        "total_debt_to_equity", "pe", "ps", "pb", "p_fcf",
        "ev_to_ebitda", "ev_to_sales", "dividend_payout",
    }

    GROUPS = {
        "business_quality": ("roe", "roic", "roa", "net_margin"),
        "growth": (
            "revenue_growth", "revenue_growth_3y", "revenue_growth_5y",
            "revenue_change_5y", "eps_growth", "ebitda_growth",
        ),
        "cash_generation": ("free_cash_flow", "free_cash_flow_to_price"),
        "financial_health": (
            "current_ratio", "net_debt_to_ebitda", "total_debt_to_ebitda",
            "total_debt_to_equity",
        ),
        "valuation": ("pe", "ps", "pb", "p_fcf", "ev_to_ebitda", "ev_to_sales"),
        "shareholder_return": (
            "dividend_yield", "dividend_payout", "dividend_growth",
            "dividend_regularity",
        ),
        "fundamental_momentum": (
            "revenue_growth", "revenue_growth_3y", "revenue_growth_5y",
            "eps_growth", "ebitda_growth",
        ),
    }

    @staticmethod
    def _num(snapshot: Mapping[str, Any], metric: str) -> float | None:
        value = snapshot.get(metric)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if isfinite(number) else None

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @classmethod
    def _metric_score(cls, metric: str, value: float | None) -> float:
        if value is None:
            return 0.0
        if metric in {"pe", "ps", "pb", "p_fcf", "ev_to_ebitda", "ev_to_sales"}:
            if value <= 0:
                return 25.0
            return cls._clamp(85.0 - value * 1.5)
        if metric in {"net_debt_to_ebitda", "total_debt_to_ebitda"}:
            return cls._clamp(90.0 - max(0.0, value) * 15.0)
        if metric == "total_debt_to_equity":
            return cls._clamp(90.0 - max(0.0, value) * 45.0)
        if metric == "current_ratio":
            if value <= 0:
                return 20.0
            return cls._clamp(55.0 + (value - 1.0) * 25.0)
        if metric == "dividend_payout":
            if value < 0:
                return 25.0
            if value <= 60:
                return 80.0 + (60.0 - value) * 0.25
            return cls._clamp(80.0 - (value - 60.0) * 1.25)
        if metric == "dividend_regularity":
            return cls._clamp(value)
        if metric == "free_cash_flow_to_price":
            return cls._clamp(50.0 + value * 5.0)
        if metric == "free_cash_flow":
            if value > 0:
                return 60.0
            if value < 0:
                return 40.0
            return 50.0
        return cls._clamp(50.0 + value * 1.5)

    @classmethod
    def _metric(cls, snapshot: Mapping[str, Any], metric: str) -> FundamentalMetricResult:
        value = cls._num(snapshot, metric)
        if value is None:
            return FundamentalMetricResult(
                metric=metric,
                value=None,
                score=0.0,
                available=False,
                confidence=0.0,
                reason_codes=("METRIC_UNAVAILABLE",),
            )
        score = cls._metric_score(metric, value)
        neutral = 50.0
        if score > neutral + 10.0:
            direction = "POSITIVE"
        elif score < neutral - 10.0:
            direction = "NEGATIVE"
        else:
            direction = "NEUTRAL"
        return FundamentalMetricResult(
            metric=metric,
            value=value,
            score=score,
            available=True,
            confidence=100.0,
            direction=direction,
        )

    @classmethod
    def _group(cls, snapshot: Mapping[str, Any], name: str) -> FundamentalGroupResult:
        results = tuple(cls._metric(snapshot, metric) for metric in cls.GROUPS[name])
        available = tuple(item for item in results if item.available)
        coverage = len(available) / len(results) * 100.0 if results else 0.0
        if not available:
            return FundamentalGroupResult(
                name=name,
                score=0.0,
                confidence=0.0,
                coverage=0.0,
                metrics=results,
                reason_codes=("GROUP_UNAVAILABLE",),
            )
        score = mean(item.score for item in available)
        confidence = mean(item.confidence for item in available) * coverage / 100.0
        reasons: list[str] = []
        if coverage < 50.0:
            reasons.append("LOW_DATA_COVERAGE")
        elif coverage < 100.0:
            reasons.append("PARTIAL_DATA_COVERAGE")
        return FundamentalGroupResult(
            name=name,
            score=cls._clamp(score),
            confidence=cls._clamp(confidence),
            coverage=coverage,
            metrics=results,
            reason_codes=tuple(reasons),
        )

    @classmethod
    def _momentum(cls, snapshot: Mapping[str, Any]) -> FundamentalGroupResult:
        metrics = tuple(cls._metric(snapshot, metric) for metric in cls.GROUPS["fundamental_momentum"])
        available = tuple(item for item in metrics if item.available)
        if not available:
            return FundamentalGroupResult("fundamental_momentum", 0.0, 0.0, 0.0, metrics, ("GROUP_UNAVAILABLE",))
        values = {item.metric: item.value for item in available}
        trend_pairs = (
            (values.get("revenue_growth_5y"), values.get("revenue_growth_3y")),
            (values.get("revenue_growth_3y"), values.get("revenue_growth")),
        )
        accelerations = [short - long for long, short in trend_pairs if long is not None and short is not None]
        acceleration_score = cls._clamp(50.0 + mean(accelerations) * 2.0) if accelerations else 50.0
        base_score = mean(item.score for item in available)
        score = cls._clamp(base_score * 0.7 + acceleration_score * 0.3)
        coverage = len(available) / len(metrics) * 100.0
        confidence = cls._clamp(mean(item.confidence for item in available) * coverage / 100.0)
        reasons: list[str] = []
        if accelerations:
            if mean(accelerations) > 2.0:
                reasons.append("FUNDAMENTAL_ACCELERATION")
            elif mean(accelerations) < -2.0:
                reasons.append("FUNDAMENTAL_DECELERATION")
        if coverage < 100.0:
            reasons.append("PARTIAL_DATA_COVERAGE")
        return FundamentalGroupResult("fundamental_momentum", score, confidence, coverage, metrics, tuple(reasons))

    @classmethod
    def analyze(cls, fundamentals: Any = None) -> FundamentalAnalysisResult:
        if not isinstance(fundamentals, Mapping) or not fundamentals:
            empty = tuple(
                FundamentalGroupResult(name, 0.0, 0.0, 0.0, (), ("GROUP_UNAVAILABLE",))
                for name in cls.GROUPS
            )
            groups = {group.name: group for group in empty}
            return FundamentalAnalysisResult(
                business_quality=groups["business_quality"],
                growth=groups["growth"],
                cash_generation=groups["cash_generation"],
                financial_health=groups["financial_health"],
                valuation=groups["valuation"],
                shareholder_return=groups["shareholder_return"],
                fundamental_momentum=groups["fundamental_momentum"],
                overall_score=0.0,
                confidence=0.0,
                coverage=0.0,
                status="UNAVAILABLE",
                reason_codes=("NO_FUNDAMENTAL_DATA",),
            )

        business_quality = cls._group(fundamentals, "business_quality")
        growth = cls._group(fundamentals, "growth")
        cash_generation = cls._group(fundamentals, "cash_generation")
        financial_health = cls._group(fundamentals, "financial_health")
        valuation = cls._group(fundamentals, "valuation")
        shareholder_return = cls._group(fundamentals, "shareholder_return")
        momentum = cls._momentum(fundamentals)
        groups = (
            business_quality, growth, cash_generation, financial_health,
            valuation, shareholder_return, momentum,
        )
        available_groups = tuple(group for group in groups if group.coverage > 0)
        overall = mean(group.score for group in available_groups) if available_groups else 0.0
        coverage = mean(group.coverage for group in groups) if groups else 0.0
        confidence = mean(group.confidence for group in available_groups) if available_groups else 0.0
        if coverage == 0:
            status = "UNAVAILABLE"
        elif coverage < 50:
            status = "PARTIAL"
        elif coverage < 100:
            status = "PARTIAL"
        else:
            status = "AVAILABLE"
        reasons: list[str] = []
        if coverage < 100:
            reasons.append("PARTIAL_DATA_COVERAGE")
        return FundamentalAnalysisResult(
            business_quality=business_quality,
            growth=growth,
            cash_generation=cash_generation,
            financial_health=financial_health,
            valuation=valuation,
            shareholder_return=shareholder_return,
            fundamental_momentum=momentum,
            overall_score=cls._clamp(overall),
            confidence=cls._clamp(confidence),
            coverage=cls._clamp(coverage),
            status=status,
            reason_codes=tuple(reasons),
        )


__all__ = [
    "FUNDAMENTAL_ANALYSIS_VERSION",
    "FundamentalMetricResult",
    "FundamentalGroupResult",
    "FundamentalAnalysisResult",
    "FundamentalAnalysisServiceV082",
]
