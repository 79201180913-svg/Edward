from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from math import erf, sqrt
from statistics import mean, pstdev
from typing import Mapping, Sequence

from edward.services.analysis_service import Candle

logger = logging.getLogger(__name__)
STATISTICAL_INTEGRITY_VERSION = "0.8.14"


@dataclass(frozen=True, slots=True)
class TemporalSplitV014:
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    oos_start: int
    oos_end: int

    @property
    def train_size(self) -> int:
        return max(0, self.train_end - self.train_start)

    @property
    def validation_size(self) -> int:
        return max(0, self.validation_end - self.validation_start)

    @property
    def oos_size(self) -> int:
        return max(0, self.oos_end - self.oos_start)


@dataclass(frozen=True, slots=True)
class StatisticalIntegrityResultV014:
    observations: int
    effective_sample_size: float
    overlap_ratio_pct: float
    mean_return_pct: float
    baseline_return_pct: float
    excess_return_pct: float
    standard_error_pct: float
    z_score: float
    p_value_one_sided: float
    hypotheses_tested: int
    adjusted_p_value: float
    multiple_testing_valid: bool
    overlap_valid: bool
    statistically_valid: bool


class TradingPathStatisticalIntegrityServiceV014:
    """TRAIN/VALIDATION statistical controls for adaptive path discovery.

    Statistical integrity is based on actual event-window overlap when event indices
    are available, and uses a family-wise Holm correction across the candidate family.
    No OOS candles are accepted by this service.
    """

    VERSION = STATISTICAL_INTEGRITY_VERSION
    MIN_TRAIN_SIZE = 60
    MIN_VALIDATION_SIZE = 20
    MIN_OOS_SIZE = 20
    MIN_EFFECTIVE_SAMPLE_SIZE = 8.0
    ALPHA = 0.05

    @classmethod
    def temporal_split(cls, candles: Sequence[Candle], *, train_ratio: float = 0.60, validation_ratio: float = 0.20) -> TemporalSplitV014:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        if not 0.0 < train_ratio < 1.0:
            raise ValueError("train_ratio must be between 0 and 1")
        if not 0.0 <= validation_ratio < 1.0:
            raise ValueError("validation_ratio must be between 0 and 1")
        if train_ratio + validation_ratio >= 1.0:
            raise ValueError("train_ratio + validation_ratio must be < 1")
        n = len(ordered)
        train_end = int(n * train_ratio)
        validation_end = train_end + int(n * validation_ratio)
        split = TemporalSplitV014(0, train_end, train_end, validation_end, validation_end, n)
        logger.warning("[V014 STAT SPLIT] candles=%d train=%d:%d validation=%d:%d oos=%d:%d", n, split.train_start, split.train_end, split.validation_start, split.validation_end, split.oos_start, split.oos_end)
        return split

    @classmethod
    def partition_candles(cls, candles: Sequence[Candle], *, train_ratio: float = 0.60, validation_ratio: float = 0.20, require_minimums: bool = True) -> tuple[tuple[Candle, ...], tuple[Candle, ...], tuple[Candle, ...]]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        split = cls.temporal_split(ordered, train_ratio=train_ratio, validation_ratio=validation_ratio)
        if require_minimums and (split.train_size < cls.MIN_TRAIN_SIZE or split.validation_size < cls.MIN_VALIDATION_SIZE or split.oos_size < cls.MIN_OOS_SIZE):
            raise ValueError("insufficient temporal partition sizes: " f"train={split.train_size}, validation={split.validation_size}, oos={split.oos_size}")
        train = ordered[split.train_start:split.train_end]
        validation = ordered[split.validation_start:split.validation_end]
        oos = ordered[split.oos_start:split.oos_end]
        logger.warning("[V014 STAT PARTITION] train=%d validation=%d oos=%d disjoint=True", len(train), len(validation), len(oos))
        return train, validation, oos

    @staticmethod
    def _one_sided_normal_pvalue(z_score: float) -> float:
        cdf = 0.5 * (1.0 + erf(z_score / sqrt(2.0)))
        return max(0.0, min(1.0, 1.0 - cdf))

    @staticmethod
    def _non_overlapping_count(observation_indices: Sequence[int], *, horizon: int) -> int:
        if not observation_indices:
            return 0
        if horizon < 1:
            raise ValueError("horizon must be positive")
        selected = 0
        last_index: int | None = None
        for index in sorted(set(int(value) for value in observation_indices)):
            if last_index is None or index >= last_index + horizon:
                selected += 1
                last_index = index
        return selected

    @classmethod
    def effective_sample_size(cls, observations: int, *, horizon: int, observation_indices: Sequence[int] | None = None) -> float:
        if observations <= 0:
            return 0.0
        if horizon < 1:
            raise ValueError("horizon must be positive")
        if observation_indices is not None:
            return float(min(observations, cls._non_overlapping_count(observation_indices, horizon=horizon)))
        return max(1.0, observations / float(horizon))

    @classmethod
    def overlap_ratio_pct(cls, observations: int, *, horizon: int, observation_indices: Sequence[int] | None = None) -> float:
        if observations <= 1:
            return 0.0
        if horizon < 1:
            raise ValueError("horizon must be positive")
        if observation_indices is not None:
            effective = cls.effective_sample_size(observations, horizon=horizon, observation_indices=observation_indices)
            return min(100.0, max(0.0, (1.0 - effective / observations) * 100.0))
        return min(100.0, max(0.0, (horizon - 1) / horizon * 100.0))

    @staticmethod
    def _holm_adjusted_p_values(p_values: Mapping[object, float]) -> dict[object, float]:
        ordered = sorted(p_values.items(), key=lambda item: (item[1], repr(item[0])))
        adjusted: dict[object, float] = {}
        running = 0.0
        count = len(ordered)
        for rank, (candidate, p_value) in enumerate(ordered, start=1):
            corrected = min(1.0, max(running, float(p_value) * (count - rank + 1)))
            running = corrected
            adjusted[candidate] = corrected
        return adjusted

    @classmethod
    def _bonferroni(cls, p_value: float, hypotheses_tested: int) -> float:
        return min(1.0, p_value * max(1, hypotheses_tested))

    @classmethod
    def evaluate(cls, returns_pct: Sequence[float], *, baseline_return_pct: float, horizon: int, hypotheses_tested: int, observation_indices: Sequence[int] | None = None, adjusted_p_value: float | None = None) -> StatisticalIntegrityResultV014:
        values = tuple(float(value) for value in returns_pct)
        observations = len(values)
        if observations == 0:
            return StatisticalIntegrityResultV014(0, 0.0, 0.0, 0.0, float(baseline_return_pct), 0.0, 0.0, 0.0, 1.0, max(1, hypotheses_tested), 1.0, False, False, False)
        if horizon < 1:
            raise ValueError("horizon must be positive")
        if hypotheses_tested < 1:
            raise ValueError("hypotheses_tested must be >= 1")
        effective_n = cls.effective_sample_size(observations, horizon=horizon, observation_indices=observation_indices)
        overlap_ratio = cls.overlap_ratio_pct(observations, horizon=horizon, observation_indices=observation_indices)
        event_mean = mean(values)
        excess = event_mean - float(baseline_return_pct)
        dispersion = pstdev(values) if observations > 1 else 0.0
        if dispersion > 0.0 and effective_n > 0.0:
            standard_error = dispersion / sqrt(effective_n)
            z_score = excess / standard_error
            p_value = cls._one_sided_normal_pvalue(z_score)
        else:
            standard_error = 0.0
            z_score = 0.0
            p_value = 1.0
        adjusted = cls._bonferroni(p_value, hypotheses_tested) if adjusted_p_value is None else float(adjusted_p_value)
        overlap_valid = effective_n >= cls.MIN_EFFECTIVE_SAMPLE_SIZE
        multiple_testing_valid = adjusted < cls.ALPHA
        statistically_valid = excess > 0.0 and overlap_valid and multiple_testing_valid
        return StatisticalIntegrityResultV014(observations, effective_n, overlap_ratio, event_mean, float(baseline_return_pct), excess, standard_error, z_score, p_value, hypotheses_tested, adjusted, multiple_testing_valid, overlap_valid, statistically_valid)

    @classmethod
    def evaluate_candidate_returns(cls, returns_by_candidate: Mapping[object, Sequence[float]], *, baseline_return_pct_by_horizon: Mapping[int, float], horizon_by_candidate: Mapping[object, int], observation_indices_by_candidate: Mapping[object, Sequence[int]] | None = None) -> dict[object, StatisticalIntegrityResultV014]:
        hypotheses_tested = len(returns_by_candidate)
        if hypotheses_tested < 1:
            return {}
        raw: dict[object, StatisticalIntegrityResultV014] = {}
        p_values: dict[object, float] = {}
        for candidate, returns_pct in returns_by_candidate.items():
            horizon = horizon_by_candidate[candidate]
            indices = observation_indices_by_candidate.get(candidate) if observation_indices_by_candidate else None
            result = cls.evaluate(returns_pct, baseline_return_pct=baseline_return_pct_by_horizon[horizon], horizon=horizon, hypotheses_tested=hypotheses_tested, observation_indices=indices)
            raw[candidate] = result
            p_values[candidate] = result.p_value_one_sided
        adjusted_values = cls._holm_adjusted_p_values(p_values)
        results: dict[object, StatisticalIntegrityResultV014] = {}
        for candidate, result in raw.items():
            adjusted = adjusted_values[candidate]
            results[candidate] = replace(result, adjusted_p_value=adjusted, multiple_testing_valid=adjusted < cls.ALPHA, statistically_valid=result.excess_return_pct > 0.0 and result.overlap_valid and adjusted < cls.ALPHA)
        logger.warning("[V014 STAT FAMILY] candidates=%d correction=holm train_validation_only=True", hypotheses_tested)
        return results


__all__ = ["STATISTICAL_INTEGRITY_VERSION", "TemporalSplitV014", "StatisticalIntegrityResultV014", "TradingPathStatisticalIntegrityServiceV014"]
