from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Iterable, Sequence

from edward.services.analysis_service import Candle
from edward.services.forecast_model_selection_service import ForecastModelSelectionService


FORECAST_WF_VERSION = "0.5.0"


@dataclass(frozen=True, slots=True)
class ForecastWindowMetrics:
    model: str
    horizon_days: int
    train_size: int
    validation_size: int
    mae_pct: float
    rmse_pct: float
    directional_accuracy_pct: float
    hit_rate_pct: float
    score: float


@dataclass(frozen=True, slots=True)
class ForecastWalkForwardResult:
    horizon_days: int
    selected_model: str
    windows: tuple[ForecastWindowMetrics, ...]
    mean_mae_pct: float
    mean_rmse_pct: float
    mean_directional_accuracy_pct: float
    mean_hit_rate_pct: float
    stability_pct: float
    quality_score: float
    version: str = FORECAST_WF_VERSION


class ForecastWalkForwardService:
    """Point-in-time walk-forward validation for forecast models."""

    MIN_TRAIN_SIZE = 60
    TEST_SIZE = 20
    STEP_SIZE = 20

    @staticmethod
    def _returns(candles: Sequence[Candle]) -> list[float]:
        return ForecastModelSelectionService._returns(candles)

    @classmethod
    def _evaluate_window(
        cls,
        train: Sequence[Candle],
        validation: Sequence[Candle],
        model: str,
        horizon: int,
    ) -> ForecastWindowMetrics:
        errors: list[float] = []
        squared_errors: list[float] = []
        directions: list[float] = []
        max_offset = len(validation) - horizon
        if max_offset <= 0:
            max_offset = 1
        for offset in range(max_offset):
            prefix = list(train) + list(validation[: offset + 1])
            origin = prefix[-1].close
            target = validation[min(offset + horizon, len(validation) - 1)].close
            predicted = ForecastModelSelectionService._forecast_price(prefix, model, horizon)
            if target:
                error_pct = abs(predicted - target) / target * 100.0
                errors.append(error_pct)
                squared_errors.append(error_pct * error_pct)
            directions.append(1.0 if (predicted >= origin) == (target >= origin) else 0.0)

        mae = mean(errors) if errors else 100.0
        rmse = sqrt(mean(squared_errors)) if squared_errors else 100.0
        direction_accuracy = mean(directions) * 100.0 if directions else 0.0
        hit_rate = direction_accuracy
        error_score = max(0.0, min(100.0, 100.0 - mae * 10.0))
        rmse_score = max(0.0, min(100.0, 100.0 - rmse * 8.0))
        direction_score = max(0.0, min(100.0, direction_accuracy))
        score = round(error_score * 0.35 + rmse_score * 0.25 + direction_score * 0.40, 4)
        return ForecastWindowMetrics(
            model=model,
            horizon_days=horizon,
            train_size=len(train),
            validation_size=len(validation),
            mae_pct=round(mae, 6),
            rmse_pct=round(rmse, 6),
            directional_accuracy_pct=round(direction_accuracy, 4),
            hit_rate_pct=round(hit_rate, 4),
            score=score,
        )

    @classmethod
    def _windows(cls, candles: Sequence[Candle]) -> list[tuple[list[Candle], list[Candle]]]:
        ordered = sorted(candles, key=lambda item: item.timestamp)
        result: list[tuple[list[Candle], list[Candle]]] = []
        train_end = cls.MIN_TRAIN_SIZE
        while train_end + cls.TEST_SIZE <= len(ordered):
            result.append((list(ordered[:train_end]), list(ordered[train_end:train_end + cls.TEST_SIZE])))
            train_end += cls.STEP_SIZE
        return result

    @classmethod
    def validate(
        cls,
        *,
        candles: Iterable[Candle],
        horizon: int,
        models: Sequence[str] = ForecastModelSelectionService.MODELS,
    ) -> ForecastWalkForwardResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if len(ordered) < cls.MIN_TRAIN_SIZE + cls.TEST_SIZE:
            raise ValueError("Недостаточно истории для Forecast Walk Forward")
        if horizon <= 0:
            raise ValueError("Горизонт прогноза должен быть положительным")
        if horizon >= cls.TEST_SIZE:
            raise ValueError("Горизонт прогноза должен быть меньше размера validation окна")

        windows = cls._windows(ordered)
        by_model: dict[str, list[ForecastWindowMetrics]] = {}
        for model in models:
            by_model[model] = [
                cls._evaluate_window(train, validation, model, horizon)
                for train, validation in windows
            ]

        model_summaries: list[tuple[str, float, list[ForecastWindowMetrics]]] = []
        for model, metrics in by_model.items():
            average_score = mean(item.score for item in metrics) if metrics else 0.0
            model_summaries.append((model, average_score, metrics))

        selected_model, _, selected_windows = max(
            model_summaries,
            key=lambda item: (
                item[1],
                mean(metric.directional_accuracy_pct for metric in item[2]) if item[2] else 0.0,
                -(mean(metric.mae_pct for metric in item[2]) if item[2] else 100.0),
            ),
        )

        scores = [item.score for item in selected_windows]
        mean_score = mean(scores) if scores else 0.0
        score_std = pstdev(scores) if len(scores) > 1 else 0.0
        stability = max(0.0, min(100.0, mean_score - score_std))

        return ForecastWalkForwardResult(
            horizon_days=horizon,
            selected_model=selected_model,
            windows=tuple(selected_windows),
            mean_mae_pct=round(mean(item.mae_pct for item in selected_windows), 6),
            mean_rmse_pct=round(mean(item.rmse_pct for item in selected_windows), 6),
            mean_directional_accuracy_pct=round(mean(item.directional_accuracy_pct for item in selected_windows), 4),
            mean_hit_rate_pct=round(mean(item.hit_rate_pct for item in selected_windows), 4),
            stability_pct=round(stability, 4),
            quality_score=round(mean_score, 4),
        )

    @classmethod
    def validate_all(
        cls,
        *,
        candles: Iterable[Candle],
        horizons: Sequence[int],
        models: Sequence[str] = ForecastModelSelectionService.MODELS,
    ) -> tuple[ForecastWalkForwardResult, ...]:
        return tuple(
            cls.validate(candles=candles, horizon=horizon, models=models)
            for horizon in sorted(set(int(item) for item in horizons))
        )
