from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Callable, Sequence

from edward.domain import TradingPathCandidate
from edward.services.analysis_service import Candle
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSValidationServiceV012

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


@dataclass(frozen=True, slots=True)
class NestedWalkForwardFoldV015:
    index: int
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    discovered_candidates: int
    evaluated_candidates: int


@dataclass(frozen=True, slots=True)
class NestedWalkForwardResultV015:
    folds: tuple[NestedWalkForwardFoldV015, ...]
    candidate_summaries: tuple[tuple[TradingPathCandidate, WalkForwardSummaryV015], ...]


class TradingPathWalkForwardServiceV015:
    """Sequential and nested walk-forward validation.

    For nested execution, discovery is rerun independently inside every TRAIN
    fold. Validation candles are never supplied to the discovery callback.
    Candidate stability is aggregated across sequential validation folds.
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
            (0, first_train_end + offset * validation_size,
             first_train_end + offset * validation_size,
             first_train_end + (offset + 1) * validation_size)
            for offset in range(windows)
        )

    @staticmethod
    def _candidate_key(candidate: TradingPathCandidate) -> tuple[object, ...]:
        rule = candidate.rule
        return (
            rule.instrument_uid, rule.ticker, rule.hypothesis,
            rule.regime, rule.volatility_bucket, rule.direction, rule.horizon,
        )

    @classmethod
    def _aggregate_summaries(
        cls,
        evaluated: Sequence[tuple[TradingPathCandidate, WalkForwardSummaryV015]],
        *,
        expected_windows: int,
    ) -> tuple[tuple[TradingPathCandidate, WalkForwardSummaryV015], ...]:
        grouped: dict[tuple[object, ...], list[tuple[TradingPathCandidate, WalkForwardSummaryV015]]] = {}
        for candidate, summary in evaluated:
            grouped.setdefault(cls._candidate_key(candidate), []).append((candidate, summary))

        result: list[tuple[TradingPathCandidate, WalkForwardSummaryV015]] = []
        for key in sorted(grouped, key=str):
            items = grouped[key]
            windows = tuple(item.windows[0] for item in items if item.windows)
            if not windows:
                continue
            positive = sum(item.positive for item in windows)
            excess = tuple(item.excess_return_pct for item in windows)
            sufficient = len(windows) == expected_windows and all(
                item.candidate_observations >= cls.MIN_VALIDATION_OBSERVATIONS for item in windows
            )
            persistence = positive / len(windows) * 100.0
            summary = WalkForwardSummaryV015(
                windows=windows,
                wf_windows=len(windows),
                positive_windows=positive,
                persistence_pct=persistence,
                mean_excess_pct=mean(excess),
                median_excess_pct=median(excess),
                worst_window_excess_pct=min(excess),
                dispersion_pct=pstdev(excess) if len(excess) > 1 else 0.0,
                sign_consistency_pct=sum(value > 0 for value in excess) / len(excess) * 100.0,
                sample_sufficiency=sufficient,
                passed=sufficient and persistence >= 75.0 and min(excess) > 0.0,
            )
            result.append((items[-1][0], summary))
        return tuple(result)

    @classmethod
    def nested_validate(
        cls,
        candles: Sequence[Candle],
        *,
        discover: Callable[[Sequence[Candle]], Sequence[TradingPathCandidate]],
        windows: int = DEFAULT_WINDOWS,
        train_size: int = DEFAULT_TRAIN_SIZE,
        validation_size: int = DEFAULT_VALIDATION_SIZE,
        evaluator: Callable[..., object] | None = None,
    ) -> NestedWalkForwardResultV015:
        """Run discovery independently in each expanding TRAIN fold."""
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        ranges = cls.build_windows(ordered, windows=windows, train_size=train_size, validation_size=validation_size)
        if not ranges:
            return NestedWalkForwardResultV015(folds=(), candidate_summaries=())

        validation_service = evaluator or TradingPathOOSValidationServiceV012
        folds: list[NestedWalkForwardFoldV015] = []
        evaluated: list[tuple[TradingPathCandidate, WalkForwardSummaryV015]] = []

        for fold_index, (_, train_end, validation_start, validation_end) in enumerate(ranges, 1):
            train_candles = ordered[:train_end]
            discovered = tuple(discover(train_candles))
            folds.append(NestedWalkForwardFoldV015(
                index=fold_index, train_start=0, train_end=train_end,
                validation_start=validation_start, validation_end=validation_end,
                discovered_candidates=len(discovered), evaluated_candidates=len(discovered),
            ))
            for candidate in discovered:
                result = validation_service.validate(
                    candidate, ordered, windows=1, test_size=validation_size,
                    evaluation_start=validation_start, evaluation_end=validation_end,
                )
                if not result:
                    continue
                item = result[0]
                window = WalkForwardWindowV015(
                    index=fold_index, train_start=0, train_end=train_end,
                    validation_start=validation_start, validation_end=validation_end,
                    candidate_observations=item.observations,
                    mean_return_pct=item.mean_return_pct,
                    baseline_return_pct=item.baseline_return_pct,
                    excess_return_pct=item.excess_return_pct,
                    win_rate_pct=item.win_rate_pct,
                    positive=item.positive and item.observations >= cls.MIN_VALIDATION_OBSERVATIONS,
                )
                evaluated.append((candidate, WalkForwardSummaryV015(
                    windows=(window,), wf_windows=1, positive_windows=int(window.positive),
                    persistence_pct=100.0 if window.positive else 0.0,
                    mean_excess_pct=window.excess_return_pct,
                    median_excess_pct=window.excess_return_pct,
                    worst_window_excess_pct=window.excess_return_pct,
                    dispersion_pct=0.0,
                    sign_consistency_pct=100.0 if window.excess_return_pct > 0 else 0.0,
                    sample_sufficiency=window.candidate_observations >= cls.MIN_VALIDATION_OBSERVATIONS,
                    passed=window.positive,
                )))

        candidate_summaries = cls._aggregate_summaries(evaluated, expected_windows=windows)
        logger.warning(
            "[V015 NESTED WALK FORWARD] folds=%d discovered=%d evaluated=%d stable_candidates=%d",
            len(folds), sum(item.discovered_candidates for item in folds),
            sum(item.evaluated_candidates for item in folds),
            sum(summary.passed for _, summary in candidate_summaries),
        )
        return NestedWalkForwardResultV015(tuple(folds), candidate_summaries)

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
                candidate, ordered, windows=1, test_size=validation_size,
                evaluation_start=validation_start, evaluation_end=validation_end,
            )
            if not result:
                continue
            item = result[0]
            fold_results.append(WalkForwardWindowV015(
                index=fold + 1, train_start=0, train_end=validation_start,
                validation_start=validation_start, validation_end=validation_end,
                candidate_observations=item.observations,
                mean_return_pct=item.mean_return_pct,
                baseline_return_pct=item.baseline_return_pct,
                excess_return_pct=item.excess_return_pct,
                win_rate_pct=item.win_rate_pct,
                positive=item.positive and item.observations >= cls.MIN_VALIDATION_OBSERVATIONS,
            ))
        if not fold_results:
            return cls._empty_summary()
        sufficient = all(item.candidate_observations >= cls.MIN_VALIDATION_OBSERVATIONS for item in fold_results)
        positive = sum(item.positive for item in fold_results)
        excess = tuple(item.excess_return_pct for item in fold_results)
        persistence = positive / len(fold_results) * 100.0
        summary = WalkForwardSummaryV015(
            windows=tuple(fold_results), wf_windows=len(fold_results), positive_windows=positive,
            persistence_pct=persistence, mean_excess_pct=mean(excess), median_excess_pct=median(excess),
            worst_window_excess_pct=min(excess),
            dispersion_pct=pstdev(excess) if len(excess) > 1 else 0.0,
            sign_consistency_pct=sum(value > 0 for value in excess) / len(excess) * 100.0,
            sample_sufficiency=sufficient,
            passed=sufficient and persistence >= 75.0 and min(excess) > 0.0,
        )
        logger.warning(
            "[V015 WALK FORWARD] ticker=%s hypothesis=%s windows=%d positive=%d persistence=%s mean_excess=%s median_excess=%s worst_window=%s dispersion=%s sample_sufficiency=%s passed=%s",
            candidate.rule.ticker, candidate.rule.hypothesis, summary.wf_windows,
            summary.positive_windows, summary.persistence_pct, summary.mean_excess_pct,
            summary.median_excess_pct, summary.worst_window_excess_pct,
            summary.dispersion_pct, summary.sample_sufficiency, summary.passed,
        )
        return summary

    @staticmethod
    def _empty_summary() -> WalkForwardSummaryV015:
        return WalkForwardSummaryV015((), 0, 0, None, None, None, None, None, None, False, False)


__all__ = [
    "TradingPathWalkForwardServiceV015", "WalkForwardSummaryV015", "WalkForwardWindowV015",
    "NestedWalkForwardFoldV015", "NestedWalkForwardResultV015",
]
