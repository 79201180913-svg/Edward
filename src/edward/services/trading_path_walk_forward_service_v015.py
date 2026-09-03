from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Callable, Sequence

from edward.domain import TradingPathCandidate
from edward.services.analysis_service import Candle
from edward.services.trading_path_oos_validation_service_v012 import (
    TradingPathOOSValidationServiceV012,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WalkForwardWindowV015:
    index: int
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    candidate_observations: int
    mean_return_pct: float
    baseline_return_pct: float
    excess_return_pct: float
    win_rate_pct: float
    positive: bool


@dataclass(frozen=True, slots=True)
class WalkForwardSummaryV015:
    windows: tuple[WalkForwardWindowV015, ...]
    wf_windows: int
    positive_windows: int
    persistence_pct: float | None
    mean_excess_pct: float | None
    median_excess_pct: float | None
    worst_window_excess_pct: float | None
    dispersion_pct: float | None
    sign_consistency_pct: float | None
    sample_sufficiency: bool
    passed: bool


class TradingPathWalkForwardServiceV015:
    """Sequential walk-forward validation for an already discovered path.

    Discovery is deliberately supplied as a callback. The service never uses
    future validation data to construct or modify a candidate. Each fold owns a
    historical TRAIN range followed immediately by an unseen VALIDATION range.
    """

    VERSION = "0.8.15"
    DEFAULT_WINDOWS = 4
    DEFAULT_TRAIN_SIZE = 60
    DEFAULT_VALIDATION_SIZE = 30
    MIN_VALIDATION_OBSERVATIONS = 3

    @classmethod
    def build_windows(
        cls,
        candles: Sequence[Candle],
        *,
        windows: int = DEFAULT_WINDOWS,
        train_size: int = DEFAULT_TRAIN_SIZE,
        validation_size: int = DEFAULT_VALIDATION_SIZE,
    ) -> tuple[tuple[int, int, int, int], ...]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        if windows < 1 or train_size < 1 or validation_size < 1:
            raise ValueError("windows, train_size and validation_size must be positive")
        required = train_size + windows * validation_size
        if len(ordered) < required:
            return ()

        first_train_end = len(ordered) - windows * validation_size
        return tuple(
            (
                first_train_end,
                first_train_end + offset * validation_size,
                first_train_end + (offset + 1) * validation_size,
                train_size,
            )
            for offset in range(windows)
        )

    @classmethod
    def _fold_train_range(
        cls,
        fold_index: int,
        *,
        first_train_end: int,
        validation_size: int,
    ) -> tuple[int, int, int, int]:
        validation_start = first_train_end + fold_index * validation_size
        validation_end = validation_start + validation_size
        return (0, validation_start, validation_start, validation_end)

    @classmethod
    def validate_candidate(
        cls,
        candidate: TradingPathCandidate,
        candles: Sequence[Candle],
        *,
        windows: int = DEFAULT_WINDOWS,
        train_size: int = DEFAULT_TRAIN_SIZE,
        validation_size: int = DEFAULT_VALIDATION_SIZE,
        evaluator: Callable[..., object] | None = None,
    ) -> WalkForwardSummaryV015:
        """Evaluate one fixed candidate across sequential unseen validation folds.

        The candidate is an explicit output of prior TRAIN discovery. This first
        implementation therefore validates candidate persistence without silently
        rerunning discovery against the full history. Nested discovery integration
        is added by the runtime in the next step, while the fold contract remains
        reusable and independently testable.
        """
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        if len(ordered) < train_size + windows * validation_size:
            return cls._empty_summary()

        first_train_end = len(ordered) - windows * validation_size
        fold_results: list[WalkForwardWindowV015] = []
        validation_service = evaluator or TradingPathOOSValidationServiceV012

        for fold in range(windows):
            validation_start = first_train_end + fold * validation_size
            validation_end = validation_start + validation_size
            result = validation_service.validate(
                candidate,
                ordered,
                windows=1,
                test_size=validation_size,
                evaluation_start=validation_start,
                evaluation_end=validation_end,
            )
            if not result:
                fold_results.append(
                    WalkForwardWindowV015(
                        index=fold + 1,
                        train_start=0,
                        train_end=validation_start,
                        validation_start=validation_start,
                        validation_end=validation_end,
                        candidate_observations=0,
                        mean_return_pct=0.0,
                        baseline_return_pct=0.0,
                        excess_return_pct=0.0,
                        win_rate_pct=0.0,
                        positive=False,
                    )
                )
                continue
            item = result[0]
            fold_results.append(
                WalkForwardWindowV015(
                    index=fold + 1,
                    train_start=0,
                    train_end=validation_start,
                    validation_start=validation_start,
                    validation_end=validation_end,
                    candidate_observations=item.observations,
                    mean_return_pct=item.mean_return_pct,
                    baseline_return_pct=item.baseline_return_pct,
                    excess_return_pct=item.excess_return_pct,
                    win_rate_pct=item.win_rate_pct,
                    positive=item.positive and item.observations >= cls.MIN_VALIDATION_OBSERVATIONS,
                )
            )

        sufficient = bool(fold_results) and all(
            item.candidate_observations >= cls.MIN_VALIDATION_OBSERVATIONS
            for item in fold_results
        )
        positive = sum(item.positive for item in fold_results)
        excess = tuple(item.excess_return_pct for item in fold_results)
        persistence = positive / len(fold_results) * 100.0 if fold_results else None
        mean_excess = mean(excess) if excess else None
        median_excess = median(excess) if excess else None
        worst = min(excess) if excess else None
        dispersion = pstdev(excess) if len(excess) > 1 else 0.0 if excess else None
        sign_consistency = (
            sum(value > 0.0 for value in excess) / len(excess) * 100.0
            if excess else None
        )
        passed = (
            sufficient
            and persistence is not None
            and persistence >= 75.0
            and worst is not None
            and worst > 0.0
        )

        summary = WalkForwardSummaryV015(
            windows=tuple(fold_results),
            wf_windows=len(fold_results),
            positive_windows=positive,
            persistence_pct=persistence,
            mean_excess_pct=mean_excess,
            median_excess_pct=median_excess,
            worst_window_excess_pct=worst,
            dispersion_pct=dispersion,
            sign_consistency_pct=sign_consistency,
            sample_sufficiency=sufficient,
            passed=passed,
        )
        logger.warning(
            "[V015 WALK FORWARD] ticker=%s hypothesis=%s windows=%d positive=%d persistence=%s mean_excess=%s median_excess=%s worst_window=%s dispersion=%s sample_sufficiency=%s passed=%s",
            candidate.rule.ticker,
            candidate.rule.hypothesis,
            summary.wf_windows,
            summary.positive_windows,
            summary.persistence_pct,
            summary.mean_excess_pct,
            summary.median_excess_pct,
            summary.worst_window_excess_pct,
            summary.dispersion_pct,
            summary.sample_sufficiency,
            summary.passed,
        )
        return summary

    @staticmethod
    def _empty_summary() -> WalkForwardSummaryV015:
        return WalkForwardSummaryV015(
            windows=(),
            wf_windows=0,
            positive_windows=0,
            persistence_pct=None,
            mean_excess_pct=None,
            median_excess_pct=None,
            worst_window_excess_pct=None,
            dispersion_pct=None,
            sign_consistency_pct=None,
            sample_sufficiency=False,
            passed=False,
        )


__all__ = [
    "TradingPathWalkForwardServiceV015",
    "WalkForwardSummaryV015",
    "WalkForwardWindowV015",
]
