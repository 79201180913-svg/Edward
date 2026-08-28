from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Callable, Iterable, Sequence

from edward.services.analysis_service import Candle


FORECAST_QUALITY_VERSION = "0.8.0"


@dataclass(frozen=True, slots=True)
class ForecastQualityPoint:
    horizon_days: int
    observations: int
    directional_accuracy_pct: float
    mae_pct: float
    mape_pct: float
    downside_error_pct: float
    upside_error_pct: float
    probability_calibration_error_pct: float
    confidence: str


@dataclass(frozen=True, slots=True)
class ForecastCalibrationBin:
    lower_probability_pct: float
    upper_probability_pct: float
    observations: int
    predicted_probability_pct: float
    observed_positive_pct: float
    calibration_error_pct: float


@dataclass(frozen=True, slots=True)
class ForecastQualityResult:
    points: tuple[ForecastQualityPoint, ...]
    calibration: tuple[ForecastCalibrationBin, ...]
    overall_quality_score: float
    version: str = FORECAST_QUALITY_VERSION


class ForecastQualityService:
    """Measure historical forecast quality without changing ForecastResult.

    The evaluator is explicitly point-in-time: every forecast is generated only
    from candles available at its origin and is compared with future candles.
    """

    MIN_ORIGIN_OBSERVATIONS = 30
    DEFAULT_CALIBRATION_BINS = (0.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0)

    @staticmethod
    def _future_return(candles: Sequence[Candle], origin_index: int, horizon: int) -> float:
        origin = candles[origin_index].close
        target_index = origin_index + horizon
        if origin <= 0 or target_index >= len(candles):
            raise ValueError("Invalid forecast origin or horizon")
        return candles[target_index].close / origin - 1.0

    @staticmethod
    def _confidence(score: float, observations: int) -> str:
        if observations < 20:
            return "Low"
        if score >= 70.0 and observations >= 60:
            return "High"
        if score >= 50.0 and observations >= 30:
            return "Medium"
        return "Low"

    @classmethod
    def _point(
        cls,
        *,
        horizon: int,
        absolute_errors: Sequence[float],
        percentage_errors: Sequence[float],
        directions: Sequence[bool],
        downside_errors: Sequence[float],
        upside_errors: Sequence[float],
    ) -> ForecastQualityPoint:
        observations = len(directions)
        directional = mean(1.0 if item else 0.0 for item in directions) * 100.0 if directions else 0.0
        mae = mean(absolute_errors) * 100.0 if absolute_errors else 100.0
        mape = mean(percentage_errors) * 100.0 if percentage_errors else 100.0
        downside = mean(downside_errors) * 100.0 if downside_errors else 0.0
        upside = mean(upside_errors) * 100.0 if upside_errors else 0.0
        error_component = max(0.0, 100.0 - min(100.0, mape * 5.0))
        score = directional * 0.60 + error_component * 0.40
        return ForecastQualityPoint(
            horizon_days=horizon,
            observations=observations,
            directional_accuracy_pct=round(directional, 4),
            mae_pct=round(mae, 4),
            mape_pct=round(mape, 4),
            downside_error_pct=round(downside, 4),
            upside_error_pct=round(upside, 4),
            probability_calibration_error_pct=0.0,
            confidence=cls._confidence(score, observations),
        )

    @classmethod
    def evaluate(
        cls,
        *,
        candles: Iterable[Candle],
        horizons: Sequence[int],
        forecast_fn: Callable[[Sequence[Candle], int], tuple[float, float]],
        calibration_bins: Sequence[float] = DEFAULT_CALIBRATION_BINS,
    ) -> ForecastQualityResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if len(ordered) < cls.MIN_ORIGIN_OBSERVATIONS + max(horizons, default=1):
            raise ValueError("Недостаточно истории для оценки качества прогноза")

        point_results: list[ForecastQualityPoint] = []
        all_probability_pairs: list[tuple[float, bool]] = []
        for horizon in sorted({int(item) for item in horizons if int(item) > 0}):
            absolute_errors: list[float] = []
            percentage_errors: list[float] = []
            directions: list[bool] = []
            downside_errors: list[float] = []
            upside_errors: list[float] = []
            for origin_index in range(cls.MIN_ORIGIN_OBSERVATIONS - 1, len(ordered) - horizon):
                history = ordered[: origin_index + 1]
                current = history[-1].close
                expected_price, probability_up_pct = forecast_fn(history, horizon)
                actual_return = cls._future_return(ordered, origin_index, horizon)
                actual_price = current * (1.0 + actual_return)
                if actual_price <= 0 or not isfinite(expected_price):
                    continue
                error_pct = abs(expected_price - actual_price) / actual_price
                absolute_errors.append(abs(expected_price - actual_price) / current if current else 0.0)
                percentage_errors.append(error_pct)
                directions.append((expected_price >= current) == (actual_price >= current))
                downside_errors.append(max(0.0, -(expected_price - actual_price) / actual_price))
                upside_errors.append(max(0.0, (expected_price - actual_price) / actual_price))
                all_probability_pairs.append((max(0.0, min(100.0, probability_up_pct)), actual_return > 0))
            point_results.append(
                cls._point(
                    horizon=horizon,
                    absolute_errors=absolute_errors,
                    percentage_errors=percentage_errors,
                    directions=directions,
                    downside_errors=downside_errors,
                    upside_errors=upside_errors,
                )
            )

        calibration: list[ForecastCalibrationBin] = []
        edges = tuple(float(item) for item in calibration_bins)
        for lower, upper in zip(edges, edges[1:]):
            members = [item for item in all_probability_pairs if lower <= item[0] < upper or (upper == 100.0 and item[0] == 100.0)]
            if not members:
                continue
            predicted = mean(item[0] for item in members)
            observed = mean(1.0 if item[1] else 0.0 for item in members) * 100.0
            calibration.append(ForecastCalibrationBin(lower, upper, len(members), round(predicted, 4), round(observed, 4), round(abs(predicted - observed), 4)))

        calibration_error = mean(item.calibration_error_pct for item in calibration) if calibration else 100.0
        horizon_score = mean(
            item.directional_accuracy_pct * 0.60 + max(0.0, 100.0 - min(100.0, item.mape_pct * 5.0)) * 0.40
            for item in point_results
        ) if point_results else 0.0
        overall = max(0.0, min(100.0, horizon_score * 0.75 + max(0.0, 100.0 - calibration_error) * 0.25))

        if calibration:
            adjustment = calibration_error / max(1, len(calibration))
            point_results = [
                ForecastQualityPoint(
                    item.horizon_days,
                    item.observations,
                    item.directional_accuracy_pct,
                    item.mae_pct,
                    item.mape_pct,
                    item.downside_error_pct,
                    item.upside_error_pct,
                    round(adjustment, 4),
                    item.confidence,
                )
                for item in point_results
            ]

        return ForecastQualityResult(tuple(point_results), tuple(calibration), round(overall, 4))
