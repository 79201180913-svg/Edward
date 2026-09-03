from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Sequence


INDEPENDENT_OOS_EVIDENCE_VERSION_V015 = "0.8.15"


@dataclass(frozen=True, slots=True)
class TradingPathIndependentOOSEvidenceV015:
    """Immutable evidence snapshot from a locked candidate's independent OOS."""

    candidate_key: tuple[object, ...] | None
    windows: int
    observations: int
    mean_return_pct: float | None
    mean_baseline_return_pct: float | None
    excess_return_pct: float | None
    positive_windows_pct: float | None
    worst_window_excess_pct: float | None
    median_window_excess_pct: float | None
    status: str
    parameters_locked: bool
    validation_start: int | None = None
    validation_end: int | None = None
    oos_start: int | None = None
    oos_end: int | None = None
    provenance_status: str = "UNVERIFIED"
    version: str = INDEPENDENT_OOS_EVIDENCE_VERSION_V015


class TradingPathIndependentOOSEvidenceServiceV015:
    """Build decision-independent evidence from a separately evaluated OOS set.

    The service consumes already-evaluated OOS windows. It does not discover,
    mutate, re-rank, or tune the candidate and never produces a trading decision.
    The returned snapshot carries explicit candidate and temporal provenance.
    """

    MIN_WINDOWS = 1
    MIN_OBSERVATIONS = 3

    @classmethod
    def _window_bounds(cls, window: object) -> tuple[int, int] | None:
        start = getattr(window, "start", None)
        end = getattr(window, "end", None)
        if start is None or end is None:
            return None
        start_value, end_value = int(start), int(end)
        if end_value <= start_value:
            return None
        return start_value, end_value

    @classmethod
    def _provenance_bounds(cls, windows: Sequence[object]) -> tuple[int | None, int | None, bool]:
        bounds = tuple(cls._window_bounds(window) for window in windows)
        if not bounds or any(item is None for item in bounds):
            return None, None, False
        normalized = tuple(item for item in bounds if item is not None)
        ordered = tuple(sorted(normalized))
        non_overlapping = all(
            ordered[index][1] <= ordered[index + 1][0]
            for index in range(len(ordered) - 1)
        )
        return ordered[0][0], ordered[-1][1], non_overlapping

    @classmethod
    def _validate_temporal_independence(
        cls,
        oos_windows: Sequence[object],
        *,
        validation_start: int | None,
        validation_end: int | None,
    ) -> bool:
        if validation_start is None or validation_end is None:
            return True
        if validation_end <= validation_start:
            return False
        for window in oos_windows:
            bounds = cls._window_bounds(window)
            if bounds is None:
                return False
            start, end = bounds
            if start < validation_end and end > validation_start:
                return False
        return True

    @classmethod
    def _empty_result(
        cls,
        *,
        candidate_key: tuple[object, ...] | None,
        windows: int,
        validation_start: int | None,
        validation_end: int | None,
        oos_start: int | None,
        oos_end: int | None,
        status: str,
        provenance_status: str,
    ) -> TradingPathIndependentOOSEvidenceV015:
        return TradingPathIndependentOOSEvidenceV015(
            candidate_key=candidate_key,
            windows=windows,
            observations=0,
            mean_return_pct=None,
            mean_baseline_return_pct=None,
            excess_return_pct=None,
            positive_windows_pct=None,
            worst_window_excess_pct=None,
            median_window_excess_pct=None,
            status=status,
            parameters_locked=True,
            validation_start=validation_start,
            validation_end=validation_end,
            oos_start=oos_start,
            oos_end=oos_end,
            provenance_status=provenance_status,
        )

    @classmethod
    def build(
        cls,
        *,
        candidate_key: tuple[object, ...] | None,
        oos_windows: Sequence[object],
        validation_start: int | None = None,
        validation_end: int | None = None,
        oos_start: int | None = None,
        oos_end: int | None = None,
    ) -> TradingPathIndependentOOSEvidenceV015:
        """Aggregate locked OOS windows without applying a decision threshold."""
        windows = tuple(oos_windows)
        derived_oos_start, derived_oos_end, windows_valid = cls._provenance_bounds(windows)
        requested_oos_start = oos_start
        requested_oos_end = oos_end
        effective_oos_start = requested_oos_start if requested_oos_start is not None else derived_oos_start
        effective_oos_end = requested_oos_end if requested_oos_end is not None else derived_oos_end

        if not windows:
            return cls._empty_result(
                candidate_key=candidate_key,
                windows=0,
                validation_start=validation_start,
                validation_end=validation_end,
                oos_start=effective_oos_start,
                oos_end=effective_oos_end,
                status="INSUFFICIENT",
                provenance_status="UNVERIFIED",
            )

        provenance_valid = windows_valid and cls._validate_temporal_independence(
            windows,
            validation_start=validation_start,
            validation_end=validation_end,
        )
        if requested_oos_start is not None and requested_oos_start != derived_oos_start:
            provenance_valid = False
        if requested_oos_end is not None and requested_oos_end != derived_oos_end:
            provenance_valid = False
        if validation_end is not None and derived_oos_start is not None and derived_oos_start < validation_end:
            provenance_valid = False

        if not provenance_valid:
            return cls._empty_result(
                candidate_key=candidate_key,
                windows=len(windows),
                validation_start=validation_start,
                validation_end=validation_end,
                oos_start=effective_oos_start,
                oos_end=effective_oos_end,
                status="INVALID_OVERLAP",
                provenance_status="INVALID",
            )

        valid_windows = tuple(
            window
            for window in windows
            if getattr(window, "mean_return_pct", None) is not None
            and getattr(window, "baseline_return_pct", None) is not None
            and getattr(window, "excess_return_pct", None) is not None
        )
        if not valid_windows:
            return cls._empty_result(
                candidate_key=candidate_key,
                windows=len(windows),
                validation_start=validation_start,
                validation_end=validation_end,
                oos_start=effective_oos_start,
                oos_end=effective_oos_end,
                status="INSUFFICIENT",
                provenance_status="VALID",
            )

        observations = sum(int(getattr(window, "observations", 0)) for window in valid_windows)
        returns = tuple(float(window.mean_return_pct) for window in valid_windows)
        baselines = tuple(float(window.baseline_return_pct) for window in valid_windows)
        excess = tuple(float(window.excess_return_pct) for window in valid_windows)
        positive = sum(value > 0.0 for value in excess) / len(excess) * 100.0
        sufficient = len(valid_windows) >= cls.MIN_WINDOWS and observations >= cls.MIN_OBSERVATIONS

        return TradingPathIndependentOOSEvidenceV015(
            candidate_key=candidate_key,
            windows=len(valid_windows),
            observations=observations,
            mean_return_pct=round(mean(returns), 10),
            mean_baseline_return_pct=round(mean(baselines), 10),
            excess_return_pct=round(mean(excess), 10),
            positive_windows_pct=round(positive, 10),
            worst_window_excess_pct=round(min(excess), 10),
            median_window_excess_pct=round(median(excess), 10),
            status="READY" if sufficient else "INSUFFICIENT",
            parameters_locked=True,
            validation_start=validation_start,
            validation_end=validation_end,
            oos_start=effective_oos_start,
            oos_end=effective_oos_end,
            provenance_status="VALID",
        )


__all__ = [
    "INDEPENDENT_OOS_EVIDENCE_VERSION_V015",
    "TradingPathIndependentOOSEvidenceV015",
    "TradingPathIndependentOOSEvidenceServiceV015",
]
