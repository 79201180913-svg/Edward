from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from edward.services.forecast_walk_forward_service import ForecastWalkForwardResult


FORECAST_GATE_VERSION = "0.5.0"


@dataclass(frozen=True, slots=True)
class ForecastQualityGateResult:
    passed: bool
    quality_score: float
    directional_accuracy_pct: float
    stability_pct: float
    windows_count: int
    reasons: tuple[str, ...]
    version: str = FORECAST_GATE_VERSION


class ForecastQualityGateService:
    """Business gate deciding whether a forecast is reliable enough to use."""

    MIN_QUALITY_SCORE = 60.0
    MIN_DIRECTIONAL_ACCURACY_PCT = 55.0
    MIN_STABILITY_PCT = 50.0
    MIN_WINDOWS = 3

    @classmethod
    def evaluate(
        cls,
        result: ForecastWalkForwardResult,
        *,
        min_quality_score: float | None = None,
        min_directional_accuracy_pct: float | None = None,
        min_stability_pct: float | None = None,
        min_windows: int | None = None,
    ) -> ForecastQualityGateResult:
        quality_threshold = cls.MIN_QUALITY_SCORE if min_quality_score is None else float(min_quality_score)
        direction_threshold = (
            cls.MIN_DIRECTIONAL_ACCURACY_PCT
            if min_directional_accuracy_pct is None
            else float(min_directional_accuracy_pct)
        )
        stability_threshold = cls.MIN_STABILITY_PCT if min_stability_pct is None else float(min_stability_pct)
        windows_threshold = cls.MIN_WINDOWS if min_windows is None else int(min_windows)

        reasons: list[str] = []
        if result.quality_score < quality_threshold:
            reasons.append(
                f"Качество прогноза {result.quality_score:.2f} ниже порога {quality_threshold:.2f}"
            )
        if result.mean_directional_accuracy_pct < direction_threshold:
            reasons.append(
                f"Directional Accuracy {result.mean_directional_accuracy_pct:.2f}% ниже порога {direction_threshold:.2f}%"
            )
        if result.stability_pct < stability_threshold:
            reasons.append(
                f"Стабильность {result.stability_pct:.2f} ниже порога {stability_threshold:.2f}"
            )
        if len(result.windows) < windows_threshold:
            reasons.append(
                f"Недостаточно OOS-окон: {len(result.windows)} из {windows_threshold}"
            )

        return ForecastQualityGateResult(
            passed=not reasons,
            quality_score=result.quality_score,
            directional_accuracy_pct=result.mean_directional_accuracy_pct,
            stability_pct=result.stability_pct,
            windows_count=len(result.windows),
            reasons=tuple(reasons),
        )

    @classmethod
    def evaluate_all(
        cls,
        results: Iterable[ForecastWalkForwardResult],
        **kwargs,
    ) -> tuple[ForecastQualityGateResult, ...]:
        return tuple(cls.evaluate(item, **kwargs) for item in results)
