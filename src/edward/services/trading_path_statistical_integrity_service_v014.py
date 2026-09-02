from __future__ import annotations

import logging
from dataclasses import dataclass
from math import erf, sqrt
from statistics import mean, pstdev
from typing import Sequence

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

    The service provides deterministic temporal splitting, explicit partitioning of
    candles, an effective-sample-size estimate for overlapping forward-return
    observations, and a conservative Bonferroni correction for discovery tests.

    Callers must perform discovery and threshold selection only on the returned TRAIN
    partition. VALIDATION is for model/rule selection checks and OOS is a final
    untouched evaluation partition. The statistical test itself accepts only the
    supplied TRAIN/VALIDATION outcomes and has no OOS input.
    """

    VERSION = STATISTICAL_INTEGRITY_VERSION
    MIN_TRAIN_SIZE = 60
    MIN_VALIDATION_SIZE = 20
    MIN_OOS_SIZE = 20
    ALPHA = 0.05

    @classmethod
    def temporal_split(
        cls,
        candles: Sequence[Candle],
        *,
        train_ratio: float = 0.60,
        validation_ratio: float = 0.20,
    ) -> TemporalSplitV014:
        """Create a contiguous TRAIN -> VALIDATION -> OOS split."""
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
        logger.warning(
            "[V014 STAT SPLIT] candles=%d train=%d:%d validation=%d:%d oos=%d:%d",
            n, split.train_start, split.train_end, split.validation_start, split.validation_end,
            split.oos_start, split.oos_end,
        )
        return split

    @classmethod
    def partition_candles(
        cls,
        candles: Sequence[Candle],
        *,
        train_ratio: float = 0.60,
        validation_ratio: float = 0.20,
        require_minimums: bool = True,
    ) -> tuple[tuple[Candle, ...], tuple[Candle, ...], tuple[Candle, ...]]:
        """Return isolated TRAIN, VALIDATION and OOS candle partitions.

        The returned partitions are disjoint and preserve chronological order. When
        require_minimums is enabled, too-short partitions fail closed instead of
        silently allowing an invalid nested evaluation.
        """
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        split = cls.temporal_split(ordered, train_ratio=train_ratio, validation_ratio=validation_ratio)
        if require_minimums and (
            split.train_size < cls.MIN_TRAIN_SIZE
            or split.validation_size < cls.MIN_VALIDATION_SIZE
            or split.oos_size < cls.MIN_OOS_SIZE
        ):
            raise ValueError(
                "insufficient temporal partition sizes: "
                f"train={split.train_size}, validation={split.validation_size}, oos={split.oos_size}"
            )

        train = ordered[split.train_start:split.train_end]
        validation = ordered[split.validation_start:split.validation_end]
        oos = ordered[split.oos_start:split.oos_end]
        logger.warning(
            "[V014 STAT PARTITION] train=%d validation=%d oos=%d disjoint=True",
            len(train), len(validation), len(oos),
        )
        return train, validation, oos

    @staticmethod
    def _one_sided_normal_pvalue(z_score: float) -> float:
        cdf = 0.5 * (1.0 + erf(z_score / sqrt(2.0)))
        return max(0.0, min(1.0, 1.0 - cdf))

    @staticmethod
    def effective_sample_size(observations: int, *, horizon: int) -> float:
        """Conservatively reduce N for overlapping forward-return windows."""
        if observations <= 0:
            return 0.0
        if horizon < 1:
            raise ValueError("horizon must be positive")
        return max(1.0, observations / float(horizon))

    @classmethod
    def overlap_ratio_pct(cls, observations: int, *, horizon: int) -> float:
        if observations <= 1:
            return 0.0
        if horizon < 1:
            raise ValueError("horizon must be positive")
        return min(100.0, max(0.0, (horizon - 1) / horizon * 100.0))

    @classmethod
    def _bonferroni(cls, p_value: float, hypotheses_tested: int) -> float:
        count = max(1, hypotheses_tested)
        return min(1.0, p_value * count)

    @classmethod
    def evaluate(
        cls,
        returns_pct: Sequence[float],
        *,
        baseline_return_pct: float,
        horizon: int,
        hypotheses_tested: int,
    ) -> StatisticalIntegrityResultV014:
        """Evaluate supplied TRAIN/VALIDATION outcomes without touching OOS data."""
        values = tuple(float(value) for value in returns_pct)
        observations = len(values)
        if observations == 0:
            return StatisticalIntegrityResultV014(
                0, 0.0, 0.0, 0.0, float(baseline_return_pct), 0.0, 0.0, 0.0, 1.0,
                max(1, hypotheses_tested), 1.0, False, False, False,
            )
        if horizon < 1:
            raise ValueError("horizon must be positive")
        if hypotheses_tested < 1:
            raise ValueError("hypotheses_tested must be >= 1")

        effective_n = cls.effective_sample_size(observations, horizon=horizon)
        overlap_ratio = cls.overlap_ratio_pct(observations, horizon=horizon)
        event_mean = mean(values)
        excess = event_mean - float(baseline_return_pct)
        dispersion = pstdev(values) if observations > 1 else 0.0
        if dispersion > 0.0:
            standard_error = dispersion / sqrt(effective_n)
            z_score = excess / standard_error
            p_value = cls._one_sided_normal_pvalue(z_score)
        else:
            standard_error = 0.0
            z_score = 0.0
            p_value = 1.0

        adjusted = cls._bonferroni(p_value, hypotheses_tested)
        overlap_valid = effective_n >= 8.0
        multiple_testing_valid = adjusted < cls.ALPHA
        statistically_valid = excess > 0.0 and overlap_valid and multiple_testing_valid

        result = StatisticalIntegrityResultV014(
            observations=observations,
            effective_sample_size=effective_n,
            overlap_ratio_pct=overlap_ratio,
            mean_return_pct=event_mean,
            baseline_return_pct=float(baseline_return_pct),
            excess_return_pct=excess,
            standard_error_pct=standard_error,
            z_score=z_score,
            p_value_one_sided=p_value,
            hypotheses_tested=hypotheses_tested,
            adjusted_p_value=adjusted,
            multiple_testing_valid=multiple_testing_valid,
            overlap_valid=overlap_valid,
            statistically_valid=statistically_valid,
        )
        logger.warning(
            "[V014 STAT INTEGRITY] N=%d effective_N=%.3f overlap=%.2f%% excess=%.6f "
            "z=%.4f p=%.6g hypotheses=%d adjusted_p=%.6g overlap_valid=%s "
            "multiple_testing_valid=%s statistically_valid=%s train_validation_only=True",
            result.observations, result.effective_sample_size, result.overlap_ratio_pct,
            result.excess_return_pct, result.z_score, result.p_value_one_sided,
            result.hypotheses_tested, result.adjusted_p_value, result.overlap_valid,
            result.multiple_testing_valid, result.statistically_valid,
        )
        return result


__all__ = [
    "STATISTICAL_INTEGRITY_VERSION",
    "TemporalSplitV014",
    "StatisticalIntegrityResultV014",
    "TradingPathStatisticalIntegrityServiceV014",
]
