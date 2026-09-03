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
    version: str = INDEPENDENT_OOS_EVIDENCE_VERSION_V015


class TradingPathIndependentOOSEvidenceServiceV015:
    """Build decision-independent evidence from a separately evaluated OOS set.

    The service consumes already-evaluated OOS windows. It does not discover,
    mutate, re-rank, or tune the candidate and never produces a trading decision.
    """

    MIN_WINDOWS = 1
    MIN_OBSERVATIONS = 3

    @classmethod
    def _window_bounds(cls, window: object) -> tuple[int, int] | None:
        start = getattr(window, "start", None)
        end = getattr(window, "end", None)
        if start is None or end is None:
            return None
        return int(start), int(end)

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
        for window in oos_windows:
            bounds = cls._window_bounds(window)
            if bounds is None:
                return False
            start, end = bounds
            if start < validation_end and end > validation_start:
                return False
        return True

    @classmethod
    def build(
        cls,
        *,
        candidate_key: tuple[object, ...] | None,
        oos_windows: Sequence[object],
        validation_start: int | None = None,
        validation_end: int | None = None,
    ) -> TradingPathIndependentOOSEvidenceV015:
        """Aggregate locked OOS windows without applying a decision threshold."""
        windows = tuple(oos_windows)
        if not windows:
            return TradingPathIndependentOOSEvidenceV015(
                candidate_key=candidate_key,
                windows=0,
                observations=0,
                mean_return_pct=None,
                mean_baseline_return_pct=None,
                excess_return_pct=None,
                positive_windows_pct=None,
                worst_window_excess_pct=None,
                median_window_excess_pct=None,
                status="INSUFFICIENT",
                parameters_locked=True,
            )

        if not cls._validate_temporal_independence(
            windows,
            validation_start=validation_start,
            validation_end=validation_end,
        ):
            return TradingPathIndependentOOSEvidenceV015(
                candidate_key=candidate_key,
                windows=len(windows),
                observations=0,
                mean_return_pct=None,
                mean_baseline_return_pct=None,
                excess_return_pct=None,
                positive_windows_pct=None,
                worst_window_excess_pct=None,
                median_window_excess_pct=None,
                status="INVALID_OVERLAP",
                parameters_locked=True,
            )

        valid_windows = tuple(
            window
            for window in windows
            if getattr(window, "mean_return_pct", None) is not None
            and getattr(window, "baseline_return_pct", None) is not None
            and getattr(window, "excess_return_pct", None) is not None
        )
        if not valid_windows:
            return TradingPathIndependentOOSEvidenceV015(
                candidate_key=candidate_key,
                windows=len(windows),
                observations=0,
                mean_return_pct=None,
                mean_baseline_return_pct=None,
                excess_return_pct=None,
                positive_windows_pct=None,
                worst_window_excess_pct=None,
                median_window_excess_pct=None,
                status="INSUFFICIENT",
                parameters_locked=True,
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
        )


__all__ = [
    "INDEPENDENT_OOS_EVIDENCE_VERSION_V015",
    "TradingPathIndependentOOSEvidenceV015",
    "TradingPathIndependentOOSEvidenceServiceV015",
]
