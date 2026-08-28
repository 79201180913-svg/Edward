from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Any, Mapping
import logging

from .fundamental_scoring_engine_v082 import FundamentalScoringEngineV082

FUNDAMENTAL_ANALYSIS_VERSION = "0.8.2"
logger = logging.getLogger(__name__)


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
    """Structured fundamental analysis over existing v0.8.1 mapped data."""

    GROUPS = {
        "business_quality": ("roe", "roic", "roa", "net_margin"),
        "growth": (
            "revenue_growth",
            "revenue_growth_3y",
            "revenue_growth_5y",
            "revenue_change_5y",
            "eps_growth",
            "ebitda_growth",
        ),
        "cash_generation": ("free_cash_flow", "free_cash_flow_to_price"),
        "financial_health": (
            "current_ratio",
            "net_debt_to_ebitda",
            "total_debt_to_ebitda",
            "total_debt_to_equity",
        ),
        "valuation": ("pe", "ps", "pb", "p_fcf", "ev_to_ebitda", "ev_to_sales"),
        "shareholder_return": (
            "dividend_yield",
            "dividend_payout",
            "dividend_growth",
            "dividend_regularity",
        ),
        "fundamental_momentum": (
            "revenue_growth",
            "revenue_growth_3y",
            "revenue_growth_5y",
            "eps_growth",
            "ebitda_growth",
        ),
    }

    # Keep cumulative revenue change visible as evidence, but do not score it
    # as a second independent growth metric alongside normalized growth rates.
    SCORE_METRICS = {
        "growth": (
            "revenue_growth",
            "revenue_growth_3y",
            "revenue_growth_5y",
            "eps_growth",
            "ebitda_growth",
        ),
    }

    STRATEGY_WEIGHTS = {
        "long_term": {
            "business_quality": 0.25,
            "growth": 0.20,
            "cash_generation": 0.10,
            "financial_health": 0.20,
            "valuation": 0.20,
            "shareholder_return": 0.05,
            "fundamental_momentum": 0.0,
        },
        "medium_term": {
            "business_quality": 0.15,
            "growth": 0.15,
            "cash_generation": 0.05,
            "financial_health": 0.10,
            "valuation": 0.10,
            "shareholder_return": 0.05,
            "fundamental_momentum": 0.40,
        },
        "speculative": {
            "business_quality": 0.05,
            "growth": 0.05,
            "cash_generation": 0.05,
            "financial_health": 0.10,
            "valuation": 0.05,
            "shareholder_return": 0.05,
            "fundamental_momentum": 0.65,
        },
    }

    PROFILE_ALIASES = {
        "long": "long_term",
        "longterm": "long_term",
        "long-term": "long_term",
        "medium": "medium_term",
        "medium-term": "medium_term",
        "swing": "medium_term",
        "short": "speculative",
        "short_term": "speculative",
        "short-term": "speculative",
    }

    BANK_NOT_APPLICABLE = frozenset(
        {
            "roic",
            "ebitda_growth",
            "net_debt_to_ebitda",
            "total_debt_to_ebitda",
            "current_ratio",
            "ev_to_ebitda",
            "ev_to_sales",
        }
    )

    @classmethod
    def _profile(cls, profile):
        value = str(profile or "medium_term").strip().lower()
        value = cls.PROFILE_ALIASES.get(value, value)
        return value if value in cls.STRATEGY_WEIGHTS else "medium_term"

    @staticmethod
    def _num(snapshot, metric):
        try:
            value = float(snapshot.get(metric))
        except (TypeError, ValueError, AttributeError):
            return None
        return value if isfinite(value) else None

    @staticmethod
    def _context(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
        for key in ("__instrument_context", "instrument_context", "_instrument_context"):
            context = snapshot.get(key)
            if isinstance(context, Mapping):
                return context
        return {}

    @classmethod
    def _instrument_is_bank(cls, snapshot: Mapping[str, Any]) -> bool:
        context = cls._context(snapshot)
        values: list[str] = []
        for key in (
            "instrument_type",
            "instrument_type_name",
            "instrument_kind",
            "instrument_kind_name",
            "sector",
            "sector_name",
            "industry",
            "industry_name",
            "asset_class",
        ):
            value = context.get(key)
            if value is not None:
                values.append(str(value).strip().lower())
        haystack = " ".join(values)
        return any(
            token in haystack
            for token in (
                "bank",
                "banks",
                "банков",
                "банк",
                "банки",
                "banking",
            )
        )

    @classmethod
    def _not_applicable_metrics(cls, snapshot: Mapping[str, Any]) -> frozenset[str]:
        explicit: set[str] = set()
        for key in ("__not_applicable_metrics", "not_applicable_metrics"):
            value = snapshot.get(key)
            if isinstance(value, (list, tuple, set, frozenset)):
                explicit.update(str(item) for item in value)
        if cls._instrument_is_bank(snapshot):
            explicit.update(cls.BANK_NOT_APPLICABLE)
        return frozenset(explicit)

    @classmethod
    def _metric_score(cls, metric, value):
        if value is None:
            return 0.0
        e = FundamentalScoringEngineV082
        if metric in {"roe", "roic", "roa", "net_margin"}:
            return e.profitability(value, kind=metric)
        if metric in {"pe", "ps", "pb", "p_fcf", "ev_to_ebitda", "ev_to_sales"}:
            return e.valuation(value)
        if metric in {"net_debt_to_ebitda", "total_debt_to_ebitda"}:
            return e.leverage(value, scale=18.0)
        if metric == "total_debt_to_equity":
            return e.debt_to_equity(value)
        if metric == "current_ratio":
            return e.current_ratio(value)
        if metric == "dividend_payout":
            return e.payout(value)
        if metric == "free_cash_flow":
            return e.cash_flow(value)
        if metric == "free_cash_flow_to_price":
            return e.fcf_yield(value)
        if metric == "dividend_regularity":
            return e.clamp(value)
        return e.growth(value)

    @classmethod
    def _metric(cls, snapshot, metric):
        not_applicable = cls._not_applicable_metrics(snapshot)
        if metric in not_applicable:
            logger.info(
                "[V082 FUNDAMENTAL METRIC] metric=%s status=NOT_APPLICABLE value=%r context=%r",
                metric,
                snapshot.get(metric),
                dict(cls._context(snapshot)),
            )
            return FundamentalMetricResult(
                metric,
                None,
                0.0,
                False,
                0.0,
                direction="NEUTRAL",
                reason_codes=("METRIC_NOT_APPLICABLE",),
            )

        value = cls._num(snapshot, metric)
        if value is None:
            return FundamentalMetricResult(
                metric,
                None,
                0.0,
                False,
                0.0,
                reason_codes=("METRIC_UNAVAILABLE",),
            )
        score = cls._metric_score(metric, value)
        direction = "POSITIVE" if score > 60 else "NEGATIVE" if score < 40 else "NEUTRAL"
        return FundamentalMetricResult(metric, value, score, True, 100.0, direction=direction)

    @classmethod
    def _group(cls, snapshot, name):
        results = tuple(cls._metric(snapshot, m) for m in cls.GROUPS[name])
        score_metrics = set(cls.SCORE_METRICS.get(name, cls.GROUPS[name]))
        scoring_results = tuple(x for x in results if x.metric in score_metrics)
        not_applicable = tuple(x for x in scoring_results if "METRIC_NOT_APPLICABLE" in x.reason_codes)
        applicable = tuple(x for x in scoring_results if x not in not_applicable)
        available = tuple(x for x in applicable if x.available)
        coverage = len(available) / len(applicable) * 100.0 if applicable else 0.0
        excluded_from_score = tuple(x for x in results if x.metric not in score_metrics)

        if not applicable:
            reasons = ["ALL_METRICS_NOT_APPLICABLE"]
            if excluded_from_score:
                reasons.append("EVIDENCE_METRICS_EXCLUDED_FROM_SCORE")
            return FundamentalGroupResult(name, 0.0, 0.0, 0.0, results, tuple(reasons))
        if not available:
            reasons = ["GROUP_UNAVAILABLE"]
            if excluded_from_score:
                reasons.append("EVIDENCE_METRICS_EXCLUDED_FROM_SCORE")
            return FundamentalGroupResult(name, 0.0, 0.0, 0.0, results, tuple(reasons))

        score = mean(x.score for x in available)
        reasons = []
        if name == "business_quality":
            penalty = FundamentalScoringEngineV082.roe_quality_adjustment(
                cls._num(snapshot, "roe"),
                cls._num(snapshot, "total_debt_to_equity"),
            )
            score = FundamentalScoringEngineV082.clamp(score - penalty)
            if penalty > 0:
                reasons.append("ROE_LEVERAGE_ADJUSTMENT")
        if coverage < 50:
            reasons.append("LOW_DATA_COVERAGE")
        elif coverage < 100:
            reasons.append("PARTIAL_DATA_COVERAGE")
        if not_applicable:
            reasons.append("METRICS_NOT_APPLICABLE")
        if excluded_from_score:
            reasons.append("EVIDENCE_METRICS_EXCLUDED_FROM_SCORE")

        confidence = FundamentalScoringEngineV082.clamp(
            mean(x.confidence for x in available) * coverage / 100.0
        )
        logger.info(
            "[V082 FUNDAMENTAL GROUP] name=%s score=%.2f coverage=%.2f confidence=%.2f "
            "available=%s not_applicable=%s excluded=%s",
            name,
            score,
            coverage,
            confidence,
            tuple(x.metric for x in available),
            tuple(x.metric for x in not_applicable),
            tuple(x.metric for x in excluded_from_score),
        )
        return FundamentalGroupResult(
            name,
            FundamentalScoringEngineV082.clamp(score),
            confidence,
            coverage,
            results,
            tuple(reasons),
        )

    @classmethod
    def _momentum(cls, snapshot):
        metrics = tuple(cls._metric(snapshot, m) for m in cls.GROUPS["fundamental_momentum"])
        not_applicable = tuple(x for x in metrics if "METRIC_NOT_APPLICABLE" in x.reason_codes)
        available = tuple(x for x in metrics if x.available)
        applicable = tuple(x for x in metrics if x not in not_applicable)
        coverage = len(available) / len(applicable) * 100.0 if applicable else 0.0

        if not applicable:
            return FundamentalGroupResult(
                "fundamental_momentum", 0.0, 0.0, 0.0, metrics, ("ALL_METRICS_NOT_APPLICABLE",)
            )
        if not available:
            return FundamentalGroupResult(
                "fundamental_momentum", 0.0, 0.0, 0.0, metrics, ("GROUP_UNAVAILABLE",)
            )

        g5, g3, g1 = (
            cls._num(snapshot, k)
            if k not in cls._not_applicable_metrics(snapshot)
            else None
            for k in ("revenue_growth_5y", "revenue_growth_3y", "revenue_growth")
        )
        acceleration = FundamentalScoringEngineV082.growth_acceleration(g5, g3, g1)
        score = FundamentalScoringEngineV082.momentum(
            growth_5y=g5,
            growth_3y=g3,
            growth_1y=g1,
            eps_growth=cls._num(snapshot, "eps_growth")
            if "eps_growth" not in cls._not_applicable_metrics(snapshot)
            else None,
            ebitda_growth=cls._num(snapshot, "ebitda_growth")
            if "ebitda_growth" not in cls._not_applicable_metrics(snapshot)
            else None,
        )
        reasons = [FundamentalScoringEngineV082.classify_acceleration(acceleration)]
        if coverage < 100:
            reasons.append("PARTIAL_DATA_COVERAGE")
        if not_applicable:
            reasons.append("METRICS_NOT_APPLICABLE")
        confidence = FundamentalScoringEngineV082.clamp(
            mean(x.confidence for x in available) * coverage / 100.0
        )
        logger.info(
            "[V082 FUNDAMENTAL MOMENTUM] score=%.2f coverage=%.2f confidence=%.2f "
            "acceleration=%.2f available=%s not_applicable=%s",
            score,
            coverage,
            confidence,
            acceleration,
            tuple(x.metric for x in available),
            tuple(x.metric for x in not_applicable),
        )
        return FundamentalGroupResult("fundamental_momentum", score, confidence, coverage, metrics, tuple(reasons))

    @classmethod
    def _weighted_overall(cls, groups, profile):
        defaults = cls.STRATEGY_WEIGHTS[profile]
        usable = tuple(g for g in groups if g.coverage > 0 and defaults.get(g.name, 0.0) > 0)
        if not usable:
            return 0.0, 0.0, ()
        total = sum(defaults[g.name] for g in usable)
        normalized = tuple((g.name, defaults[g.name] / total) for g in usable)
        normalized_map = dict(normalized)
        if "fundamental_momentum" in defaults:
            normalized_map.setdefault("fundamental_momentum", 0.0)
        ordered = tuple((name, normalized_map[name]) for name in defaults if name in normalized_map)
        overall = sum(g.score * normalized_map[g.name] for g in usable)
        confidence = sum(g.confidence * normalized_map[g.name] for g in usable)
        return FundamentalScoringEngineV082.clamp(overall), FundamentalScoringEngineV082.clamp(confidence), ordered

    @classmethod
    def analyze(cls, fundamentals=None, *, profile="medium_term"):
        selected = cls._profile(profile)
        if not isinstance(fundamentals, Mapping) or not fundamentals:
            empty = {
                name: FundamentalGroupResult(name, 0.0, 0.0, 0.0, (), ("GROUP_UNAVAILABLE",))
                for name in cls.GROUPS
            }
            return FundamentalAnalysisResult(
                *(empty[name] for name in cls.GROUPS),
                0.0,
                0.0,
                0.0,
                "UNAVAILABLE",
                selected,
                tuple(cls.STRATEGY_WEIGHTS[selected].items()),
                ("NO_FUNDAMENTAL_DATA",),
            )

        logger.info(
            "[V082 FUNDAMENTAL INPUT] profile=%s instrument_context=%r not_applicable=%s",
            selected,
            dict(cls._context(fundamentals)),
            tuple(sorted(cls._not_applicable_metrics(fundamentals))),
        )

        groups = (
            cls._group(fundamentals, "business_quality"),
            cls._group(fundamentals, "growth"),
            cls._group(fundamentals, "cash_generation"),
            cls._group(fundamentals, "financial_health"),
            cls._group(fundamentals, "valuation"),
            cls._group(fundamentals, "shareholder_return"),
            cls._momentum(fundamentals),
        )
        overall, confidence, weights = cls._weighted_overall(groups, selected)
        coverage = mean(g.coverage for g in groups)
        available = sum(g.coverage > 0 for g in groups)
        status = "UNAVAILABLE" if available == 0 else "PARTIAL" if coverage < 100 else "AVAILABLE"
        reasons = ("PARTIAL_DATA_COVERAGE",) if coverage < 100 else ()
        logger.info(
            "[V082 FUNDAMENTAL RESULT] profile=%s overall=%.2f confidence=%.2f coverage=%.2f status=%s weights=%s",
            selected,
            overall,
            confidence,
            coverage,
            status,
            weights,
        )
        return FundamentalAnalysisResult(
            *groups,
            overall,
            confidence,
            FundamentalScoringEngineV082.clamp(coverage),
            status,
            selected,
            weights,
            reasons,
        )


__all__ = [
    "FUNDAMENTAL_ANALYSIS_VERSION",
    "FundamentalMetricResult",
    "FundamentalGroupResult",
    "FundamentalAnalysisResult",
    "FundamentalAnalysisServiceV082",
]
