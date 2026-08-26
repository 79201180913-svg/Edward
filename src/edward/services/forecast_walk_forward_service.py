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
    INNER_HOLDOUT_SIZE = 20
    INNER_MIN_TRAIN_SIZE = 40

    @staticmethod
    def _returns(candles: Sequence[Candle]) -> list[float]:
        return ForecastModelSelectionService._returns(candles)

    @classmethod
    def _evaluate_window(cls, train: Sequence[Candle], validation: Sequence[Candle], model: str, horizon: int) -> ForecastWindowMetrics:
        errors: list[float] = []
        squared_errors: list[float] = []
        directions: list[float] = []
        max_offset = len(validation) - horizon
        if max_offset <= 0:
            max_offset = 1
        for offset in range(max_offset):
            prefix = list(train) + list(validation[:offset + 1])
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
        return ForecastWindowMetrics(model, horizon, len(train), len(validation), round(mae, 6), round(rmse, 6), round(direction_accuracy, 4), round(hit_rate, 4), score)

    @classmethod
    def _select_model_for_training(cls, train: Sequence[Candle], horizon: int, models: Sequence[str]) -> str:
        if len(train) < cls.INNER_MIN_TRAIN_SIZE + cls.INNER_HOLDOUT_SIZE:
            candidates: list[tuple[str, float]] = []
            for model in models:
                predicted = ForecastModelSelectionService._forecast_price(train, model, horizon)
                origin = train[-1].close
                target = train[-1].close
                error_pct = abs(predicted - target) / target * 100.0 if target else 100.0
                direction = 100.0 if (predicted >= origin) == (target >= origin) else 0.0
                score = ForecastModelSelectionService._score(error_pct, direction)
                candidates.append((model, score))
            return max(candidates, key=lambda item: (item[1], item[0]))[0]
        inner_split = len(train) - cls.INNER_HOLDOUT_SIZE
        inner_train = list(train[:inner_split])
        inner_validation = list(train[inner_split:])
        summaries: list[tuple[str, float, float, float]] = []
        for model in models:
            metrics = cls._evaluate_window(inner_train, inner_validation, model, horizon)
            summaries.append((model, metrics.score, metrics.directional_accuracy_pct, -metrics.mae_pct))
        return max(summaries, key=lambda item: (item[1], item[2], item[3], item[0]))[0]

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
    def validate(cls, *, candles: Iterable[Candle], horizon: int, models: Sequence[str] = ForecastModelSelectionService.MODELS, origin_timestamp=None) -> ForecastWalkForwardResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if origin_timestamp is not None:
            ordered = [item for item in ordered if item.timestamp <= origin_timestamp]
        if len(ordered) < cls.MIN_TRAIN_SIZE + cls.TEST_SIZE:
            raise ValueError("Недостаточно истории для Forecast Walk Forward")
        if horizon <= 0:
            raise ValueError("Горизонт прогноза должен быть положительным")
        if horizon >= cls.TEST_SIZE:
            raise ValueError("Горизонт прогноза должен быть меньше размера validation окна")
        windows = cls._windows(ordered)
        selected_windows: list[ForecastWindowMetrics] = []
        for train, validation in windows:
            selected_model = cls._select_model_for_training(train, horizon, models)
            selected_windows.append(cls._evaluate_window(train, validation, selected_model, horizon))
        model_stats: dict[str, list[ForecastWindowMetrics]] = {}
        for metric in selected_windows:
            model_stats.setdefault(metric.model, []).append(metric)
        def model_key(item: tuple[str, list[ForecastWindowMetrics]]) -> tuple[float, float, int, str]:
            name, metrics = item
            return (mean(metric.score for metric in metrics), mean(metric.directional_accuracy_pct for metric in metrics), len(metrics), name)
        selected_model = max(model_stats.items(), key=model_key)[0] if model_stats else ""
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
    def validate_all(cls, *, candles: Iterable[Candle], horizons: Sequence[int], models: Sequence[str] = ForecastModelSelectionService.MODELS, origin_timestamp=None) -> tuple[ForecastWalkForwardResult, ...]:
        return tuple(cls.validate(candles=candles, horizon=horizon, models=models, origin_timestamp=origin_timestamp) for horizon in sorted(set(int(item) for item in horizons)))
