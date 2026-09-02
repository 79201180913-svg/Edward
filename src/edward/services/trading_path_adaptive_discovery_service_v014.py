from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.regime_engine_v08 import RegimeEngine
from edward.services.trading_path_feature_service_v014 import TradingPathFeatureServiceV014

logger = logging.getLogger(__name__)
ADAPTIVE_DISCOVERY_VERSION = "0.8.14"


@dataclass(frozen=True, slots=True)
class AdaptiveRuleConditionV014:
    feature: str
    operator: str
    threshold: float

    def matches(self, value: float | None) -> bool:
        if value is None:
            return False
        if self.operator == ">=":
            return value >= self.threshold
        if self.operator == "<=":
            return value <= self.threshold
        raise ValueError(f"Unsupported operator: {self.operator}")


@dataclass(frozen=True, slots=True)
class AdaptiveRuleV014:
    regime: str
    horizon: int
    conditions: tuple[AdaptiveRuleConditionV014, ...]

    @property
    def complexity(self) -> int:
        return len(self.conditions)

    @property
    def expression(self) -> str:
        parts = [f"{item.feature} {item.operator} {item.threshold:.8g}" for item in self.conditions]
        return f"regime={self.regime} AND " + " AND ".join(parts)


@dataclass(frozen=True, slots=True)
class AdaptiveDiscoveryCandidateV014:
    rule: AdaptiveRuleV014
    observations: int
    mean_forward_return_pct: float
    median_forward_return_pct: float
    win_rate_pct: float
    baseline_mean_return_pct: float
    excess_return_pct: float


@dataclass(frozen=True, slots=True)
class AdaptiveDiscoveryResultV014:
    version: str
    candles: int
    evaluated_rows: int
    threshold_percentiles: tuple[int, ...]
    candidates: tuple[AdaptiveDiscoveryCandidateV014, ...]


class TradingPathAdaptiveDiscoveryServiceV014:
    """Discover compact conditional rules from point-in-time features.

    This service is deliberately research-only. It consumes forward returns solely as
    the training objective and emits explicit rules for the later common candidate,
    OOS, risk and Quality Gate pipeline.

    Thresholds are derived from the supplied discovery sample. Therefore callers must
    pass TRAIN data only; nested OOS enforcement belongs to the later statistical
    integrity/runtime block.
    """

    VERSION = ADAPTIVE_DISCOVERY_VERSION
    HORIZONS = (1, 3, 5, 10, 20)
    THRESHOLD_PERCENTILES = (20, 40, 60, 80)
    MIN_OBSERVATIONS = 12
    MAX_CONDITIONS = 3
    SINGLE_SEEDS = 12
    MAX_RESULTS = 50
    MIN_ABS_EXCESS_PCT = 0.0

    @staticmethod
    def _quantile(values: Sequence[float], percentile: int) -> float | None:
        ordered = sorted(values)
        if not ordered:
            return None
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * percentile / 100.0
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

    @staticmethod
    def _forward_return(candles: Sequence[Candle], index: int, horizon: int) -> float | None:
        end = index + horizon
        if index < 0 or end >= len(candles):
            return None
        start = float(candles[index].close)
        finish = float(candles[end].close)
        if start <= 0 or finish <= 0:
            return None
        return (finish / start - 1.0) * 100.0

    @staticmethod
    def _feature_map(features) -> dict[tuple[str, int], float | None]:
        return {(item.name, item.index): item.value for item in features}

    @classmethod
    def _regimes(cls, candles: Sequence[Candle]) -> dict[int, str]:
        result: dict[int, str] = {}
        for index in range(len(candles)):
            result[index] = RegimeEngine.classify(candles[: index + 1]).regime
        return result

    @classmethod
    def _evaluate(
        cls,
        rule: AdaptiveRuleV014,
        rows: Sequence[tuple[int, float | None]],
        baselines: dict[int, float],
    ) -> AdaptiveDiscoveryCandidateV014 | None:
        values = [forward for index, forward in rows if forward is not None]
        if len(values) < cls.MIN_OBSERVATIONS:
            return None
        baseline = baselines[rule.horizon]
        event_mean = mean(values)
        excess = event_mean - baseline
        if excess <= cls.MIN_ABS_EXCESS_PCT:
            return None
        return AdaptiveDiscoveryCandidateV014(
            rule=rule,
            observations=len(values),
            mean_forward_return_pct=event_mean,
            median_forward_return_pct=median(values),
            win_rate_pct=sum(value > 0 for value in values) / len(values) * 100.0,
            baseline_mean_return_pct=baseline,
            excess_return_pct=excess,
        )

    @classmethod
    def run(cls, candles: Sequence[Candle]) -> AdaptiveDiscoveryResultV014:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        logger.warning(
            "[V014 ADAPTIVE DISCOVERY START] candles=%d horizons=%s percentiles=%s max_conditions=%d",
            len(ordered), cls.HORIZONS, cls.THRESHOLD_PERCENTILES, cls.MAX_CONDITIONS,
        )
        if len(ordered) < 51:
            logger.warning("[V014 ADAPTIVE DISCOVERY SKIP] reason=insufficient_history candles=%d", len(ordered))
            return AdaptiveDiscoveryResultV014(cls.VERSION, len(ordered), 0, cls.THRESHOLD_PERCENTILES, ())

        features = TradingPathFeatureServiceV014.build(ordered)
        feature_map = cls._feature_map(features)
        feature_names = tuple(sorted({item.name for item in features}))
        regimes = cls._regimes(ordered)
        baselines = {
            horizon: mean(
                value for index in range(len(ordered) - horizon)
                if (value := cls._forward_return(ordered, index, horizon)) is not None
            )
            for horizon in cls.HORIZONS
        }

        rows_by_regime_horizon: dict[tuple[str, int], list[int]] = {}
        for index in range(len(ordered)):
            for horizon in cls.HORIZONS:
                if index + horizon < len(ordered) and regimes[index] != "UNKNOWN":
                    rows_by_regime_horizon.setdefault((regimes[index], horizon), []).append(index)

        thresholds: dict[tuple[str, int], tuple[AdaptiveRuleConditionV014, ...]] = {}
        for regime in RegimeEngine.REGIMES:
            for horizon in cls.HORIZONS:
                indices = rows_by_regime_horizon.get((regime, horizon), [])
                for name in feature_names:
                    values = [
                        feature_map[(name, index)]
                        for index in indices
                        if feature_map[(name, index)] is not None
                    ]
                    if len(values) < cls.MIN_OBSERVATIONS:
                        continue
                    for percentile in cls.THRESHOLD_PERCENTILES:
                        threshold = cls._quantile(values, percentile)
                        if threshold is None:
                            continue
                        thresholds.setdefault((regime, horizon), () )
                        current = list(thresholds[(regime, horizon)])
                        current.extend((
                            AdaptiveRuleConditionV014(name, ">=", threshold),
                            AdaptiveRuleConditionV014(name, "<=", threshold),
                        ))
                        thresholds[(regime, horizon)] = tuple(current)

        candidates: list[AdaptiveDiscoveryCandidateV014] = []
        for (regime, horizon), conditions in sorted(thresholds.items()):
            indices = rows_by_regime_horizon[(regime, horizon)]
            rows = [
                (index, cls._forward_return(ordered, index, horizon))
                for index in indices
            ]
            unique_conditions = tuple(dict.fromkeys(conditions))
            single_results: list[AdaptiveDiscoveryCandidateV014] = []
            for condition in unique_conditions:
                selected = [
                    row for row in rows
                    if condition.matches(feature_map[(condition.feature, row[0])])
                ]
                candidate = cls._evaluate(
                    AdaptiveRuleV014(regime, horizon, (condition,)), selected, baselines,
                )
                if candidate is not None:
                    single_results.append(candidate)
            single_results.sort(key=lambda item: (-item.excess_return_pct, -item.observations, item.rule.expression))
            seeds = single_results[:cls.SINGLE_SEEDS]
            candidates.extend(seeds)

            pool = tuple(item.rule.conditions[0] for item in seeds)
            for size in (2, 3):
                expanded: dict[tuple[AdaptiveRuleConditionV014, ...], AdaptiveDiscoveryCandidateV014] = {}
                for left_index in range(len(pool)):
                    for right_index in range(left_index + 1, len(pool)):
                        pair = (pool[left_index], pool[right_index])
                        if len({condition.feature for condition in pair}) != size and size == 2:
                            continue
                        if size == 3:
                            continue
                        selected = [
                            row for row in rows
                            if all(condition.matches(feature_map[(condition.feature, row[0])]) for condition in pair)
                        ]
                        candidate = cls._evaluate(AdaptiveRuleV014(regime, horizon, pair), selected, baselines)
                        if candidate is not None:
                            expanded[pair] = candidate
                if size == 2:
                    candidates.extend(expanded.values())
                    triples_seed = tuple(sorted(expanded.values(), key=lambda item: (-item.excess_return_pct, item.rule.expression))[:8])
                    for first in range(len(triples_seed)):
                        for second in range(first + 1, len(triples_seed)):
                            a = triples_seed[first].rule.conditions
                            b = triples_seed[second].rule.conditions
                            merged = tuple(dict.fromkeys(a + b))
                            if len(merged) != 3 or len({condition.feature for condition in merged}) != 3:
                                continue
                            selected = [
                                row for row in rows
                                if all(condition.matches(feature_map[(condition.feature, row[0])]) for condition in merged)
                            ]
                            candidate = cls._evaluate(AdaptiveRuleV014(regime, horizon, merged), selected, baselines)
                            if candidate is not None:
                                candidates.append(candidate)

        dedup: dict[tuple, AdaptiveDiscoveryCandidateV014] = {}
        for candidate in candidates:
            key = (candidate.rule.regime, candidate.rule.horizon, candidate.rule.conditions)
            previous = dedup.get(key)
            if previous is None or candidate.excess_return_pct > previous.excess_return_pct:
                dedup[key] = candidate
        ordered_candidates = sorted(
            dedup.values(),
            key=lambda item: (-item.excess_return_pct, -item.observations, item.rule.complexity, item.rule.expression),
        )[:cls.MAX_RESULTS]
        logger.warning(
            "[V014 ADAPTIVE DISCOVERY RESULT] evaluated_rows=%d raw_candidates=%d unique_candidates=%d",
            sum(len(value) for value in rows_by_regime_horizon.values()), len(candidates), len(ordered_candidates),
        )
        for candidate in ordered_candidates:
            logger.warning(
                "[V014 ADAPTIVE RULE] regime=%s horizon=%d complexity=%d N=%d excess=%.6f win_rate=%.2f rule=%s",
                candidate.rule.regime, candidate.rule.horizon, candidate.rule.complexity,
                candidate.observations, candidate.excess_return_pct, candidate.win_rate_pct,
                candidate.rule.expression,
            )
        return AdaptiveDiscoveryResultV014(
            cls.VERSION,
            len(ordered),
            sum(len(value) for value in rows_by_regime_horizon.values()),
            cls.THRESHOLD_PERCENTILES,
            tuple(ordered_candidates),
        )


__all__ = [
    "ADAPTIVE_DISCOVERY_VERSION",
    "AdaptiveRuleConditionV014",
    "AdaptiveRuleV014",
    "AdaptiveDiscoveryCandidateV014",
    "AdaptiveDiscoveryResultV014",
    "TradingPathAdaptiveDiscoveryServiceV014",
]
