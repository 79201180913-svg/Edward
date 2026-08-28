from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Any, Mapping

from .fundamental_scoring_engine_v082 import FundamentalScoringEngineV082

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
    strategy_profile: str = "medium_term"
    group_weights: tuple[tuple[str, float], ...] = ()
    reason_codes: tuple[str, ...] = ()
    version: str = FUNDAMENTAL_ANALYSIS_VERSION

class FundamentalAnalysisServiceV082:
    GROUPS = {
        "business_quality": ("roe", "roic", "roa", "net_margin"),
        "growth": ("revenue_growth", "revenue_growth_3y", "revenue_growth_5y", "revenue_change_5y", "eps_growth", "ebitda_growth"),
        "cash_generation": ("free_cash_flow", "free_cash_flow_to_price"),
        "financial_health": ("current_ratio", "net_debt_to_ebitda", "total_debt_to_ebitda", "total_debt_to_equity"),
        "valuation": ("pe", "ps", "pb", "p_fcf", "ev_to_ebitda", "ev_to_sales"),
        "shareholder_return": ("dividend_yield", "dividend_payout", "dividend_growth", "dividend_regularity"),
        "fundamental_momentum": ("revenue_growth", "revenue_growth_3y", "revenue_growth_5y", "eps_growth", "ebitda_growth"),
    }
    STRATEGY_WEIGHTS = {
        "long_term": {"business_quality": .25, "growth": .20, "cash_generation": .10, "financial_health": .20, "valuation": .20, "shareholder_return": .05, "fundamental_momentum": 0.0},
        "medium_term": {"business_quality": .15, "growth": .15, "cash_generation": .05, "financial_health": .10, "valuation": .10, "shareholder_return": .05, "fundamental_momentum": .40},
        "speculative": {"business_quality": .05, "growth": .05, "cash_generation": .05, "financial_health": .10, "valuation": .05, "shareholder_return": .05, "fundamental_momentum": .65},
    }
    PROFILE_ALIASES = {"long": "long_term", "longterm": "long_term", "long-term": "long_term", "medium": "medium_term", "medium-term": "medium_term", "swing": "medium_term", "short": "speculative", "short_term": "speculative", "short-term": "speculative"}

    @classmethod
    def _profile(cls, profile: str | None) -> str:
        value = str(profile or "medium_term").strip().lower()
        value = cls.PROFILE_ALIASES.get(value, value)
        return value if value in cls.STRATEGY_WEIGHTS else "medium_term"

    @staticmethod
    def _num(snapshot: Mapping[str, Any], metric: str) -> float | None:
        try: value = float(snapshot.get(metric))
        except (TypeError, ValueError): return None
        return value if isfinite(value) else None

    @classmethod
    def _metric_score(cls, metric: str, value: float | None) -> float:
        if value is None: return 0.0
        engine = FundamentalScoringEngineV082
        if metric in {"pe", "ps", "pb", "p_fcf", "ev_to_ebitda", "ev_to_sales"}: return engine.valuation(value)
        if metric in {"net_debt_to_ebitda", "total_debt_to_ebitda"}: return engine.leverage(value, scale=18.0)
        if metric == "total_debt_to_equity": return engine.debt_to_equity(value)
        if metric == "current_ratio": return engine.current_ratio(value)
        if metric == "dividend_payout": return engine.payout(value)
        if metric == "free_cash_flow": return engine.cash_flow(value)
        if metric == "free_cash_flow_to_price": return engine.growth(value)
        if metric == "dividend_regularity": return engine.clamp(value)
        return engine.growth(value)

    @classmethod
    def _metric(cls, snapshot: Mapping[str, Any], metric: str) -> FundamentalMetricResult:
        value = cls._num(snapshot, metric)
        if value is None: return FundamentalMetricResult(metric, None, 0.0, False, 0.0, reason_codes=("METRIC_UNAVAILABLE",))
        score = cls._metric_score(metric, value)
        direction = "POSITIVE" if score > 60 else "NEGATIVE" if score < 40 else "NEUTRAL"
        return FundamentalMetricResult(metric, value, score, True, 100.0, direction=direction)

    @classmethod
    def _group(cls, snapshot: Mapping[str, Any], name: str) -> FundamentalGroupResult:
        results = tuple(cls._metric(snapshot, metric) for metric in cls.GROUPS[name])
        available = tuple(item for item in results if item.available)
        coverage = len(available) / len(results) * 100.0 if results else 0.0
        if not available: return FundamentalGroupResult(name, 0.0, 0.0, 0.0, results, ("GROUP_UNAVAILABLE",))
        score = mean(item.score for item in available)
        reasons: list[str] = []
        if name == "business_quality":
            roe = cls._num(snapshot, "roe"); debt_to_equity = cls._num(snapshot, "total_debt_to_equity")
            penalty = FundamentalScoringEngineV082.roe_quality_adjustment(roe, debt_to_equity)
            score = FundamentalScoringEngineV082.clamp(score - penalty)
            if penalty > 0: reasons.append("ROE_LEVERAGE_ADJUSTMENT")
        if coverage < 50: reasons.append("LOW_DATA_COVERAGE")
        elif coverage < 100: reasons.append("PARTIAL_DATA_COVERAGE")
        confidence = FundamentalScoringEngineV082.clamp(mean(item.confidence for item in available) * coverage / 100.0)
        return FundamentalGroupResult(name, FundamentalScoringEngineV082.clamp(score), confidence, coverage, results, tuple(reasons))

    @classmethod
    def _momentum(cls, snapshot: Mapping[str, Any]) -> FundamentalGroupResult:
        metrics = tuple(cls._metric(snapshot, metric) for metric in cls.GROUPS["fundamental_momentum"])
        available = tuple(item for item in metrics if item.available)
        if not available: return FundamentalGroupResult("fundamental_momentum", 0.0, 0.0, 0.0, metrics, ("GROUP_UNAVAILABLE",))
        g5 = cls._num(snapshot, "revenue_growth_5y"); g3 = cls._num(snapshot, "revenue_growth_3y"); g1 = cls._num(snapshot, "revenue_growth")
        acceleration = FundamentalScoringEngineV082.growth_acceleration(g5, g3, g1)
        score = FundamentalScoringEngineV082.momentum(growth_5y=g5, growth_3y=g3, growth_1y=g1, eps_growth=cls._num(snapshot, "eps_growth"), ebitda_growth=cls._num(snapshot, "ebitda_growth"))
        coverage = len(available) / len(metrics) * 100.0
        reasons = [FundamentalScoringEngineV082.classify_acceleration(acceleration)]
        if coverage < 100: reasons.append("PARTIAL_DATA_COVERAGE")
        confidence = FundamentalScoringEngineV082.clamp(mean(item.confidence for item in available) * coverage / 100.0)
        return FundamentalGroupResult("fundamental_momentum", score, confidence, coverage, metrics, tuple(reasons))

    @classmethod
    def _weighted_overall(cls, groups: tuple[FundamentalGroupResult, ...], profile: str):
        defaults = cls.STRATEGY_WEIGHTS[profile]
        usable = tuple(group for group in groups if group.coverage > 0 and defaults.get(group.name, 0.0) > 0)
        total = sum(defaults[group.name] for group in usable)
        normalized_map = {name: 0.0 for name in defaults}
        if not usable: return 0.0, 0.0, tuple(normalized_map.items())
        for group in usable: normalized_map[group.name] = defaults[group.name] / total
        overall = sum(group.score * normalized_map[group.name] for group in usable)
        confidence = sum(group.confidence * normalized_map[group.name] for group in usable)
        return FundamentalScoringEngineV082.clamp(overall), FundamentalScoringEngineV082.clamp(confidence), tuple(normalized_map.items())

    @classmethod
    def analyze(cls, fundamentals: Any = None, *, profile: str = "medium_term") -> FundamentalAnalysisResult:
        selected_profile = cls._profile(profile)
        if not isinstance(fundamentals, Mapping) or not fundamentals:
            empty = {name: FundamentalGroupResult(name, 0.0, 0.0, 0.0, (), ("GROUP_UNAVAILABLE",)) for name in cls.GROUPS}
            return FundamentalAnalysisResult(*(empty[name] for name in cls.GROUPS), 0.0, 0.0, 0.0, "UNAVAILABLE", selected_profile, tuple(cls.STRATEGY_WEIGHTS[selected_profile].items()), ("NO_FUNDAMENTAL_DATA",))
        groups = (cls._group(fundamentals, "business_quality"), cls._group(fundamentals, "growth"), cls._group(fundamentals, "cash_generation"), cls._group(fundamentals, "financial_health"), cls._group(fundamentals, "valuation"), cls._group(fundamentals, "shareholder_return"), cls._momentum(fundamentals))
        overall, confidence, normalized_weights = cls._weighted_overall(groups, selected_profile)
        coverage = mean(group.coverage for group in groups)
        available_count = sum(group.coverage > 0 for group in groups)
        status = "UNAVAILABLE" if available_count == 0 else "PARTIAL" if coverage < 100 else "AVAILABLE"
        reasons = ("PARTIAL_DATA_COVERAGE",) if coverage < 100 else ()
        return FundamentalAnalysisResult(*groups, overall, confidence, FundamentalScoringEngineV082.clamp(coverage), status, selected_profile, normalized_weights, reasons)

__all__ = ["FUNDAMENTAL_ANALYSIS_VERSION", "FundamentalMetricResult", "FundamentalGroupResult", "FundamentalAnalysisResult", "FundamentalAnalysisServiceV082"]