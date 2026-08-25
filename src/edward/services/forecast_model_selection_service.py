from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from statistics import mean, pstdev
from typing import Iterable, Sequence

from edward.services.analysis_service import Candle
from edward.services.forecast_service import (
    SUPPORTED_HORIZONS,
    ForecastPoint,
    ForecastResult,
    ForecastService,
)


MODEL_SELECTION_VERSION = "0.5.0"


@dataclass(frozen=True, slots=True)
class ForecastModelCandidate:
    name: str
    expected_price: float
    expected_return_pct: float
    absolute_error_pct: float
    directional_accuracy_pct: float
    score: float


@dataclass(frozen=True, slots=True)
class ForecastModelSelectionPoint:
    horizon_days: int
    selected_model: str
    score: float
    candidates: tuple[ForecastModelCandidate, ...]


@dataclass(frozen=True, slots=True)
class AdaptiveForecastResult:
    forecast: ForecastResult
    selections: tuple[ForecastModelSelectionPoint, ...]
    selection_version: str = MODEL_SELECTION_VERSION

    @property
    def model(self) -> str:
        models = {item.selected_model for item in self.selections}
        return next(iter(models)) if len(models) == 1 else "AdaptiveEnsemble"


class ForecastModelSelectionService:
    """Select a forecast model separately for each horizon.

    The selector evaluates transparent statistical candidates on a trailing
    holdout. No future candles are used by the candidate evaluation: the
    training prefix ends before the validation suffix.
    """

    MIN_CANDLES = 90
    HOLDOUT_SIZE = 20
    MIN_TRAIN_SIZE = 60
    MODELS = (
        "HistoricalDrift",
        "RecentDrift",
        "MomentumDrift",
        "MeanReversion",
    )

    @staticmethod
    def _returns(candles: Sequence[Candle]) -> list[float]:
        values: list[float] = []
        for previous, current in zip(candles, candles[1:]):
            if previous.close <= 0 or current.close <= 0:
                continue
            values.append(log(current.close / previous.close))
        return values

    @staticmethod
    def _predict_return(candles: Sequence[Candle], model: str, horizon: int) -> float:
        returns = ForecastModelSelectionService._returns(candles)
        if not returns:
            return 0.0
        if model == "HistoricalDrift":
            mu = mean(returns)
        elif model == "RecentDrift":
            mu = mean(returns[-30:])
        elif model == "MomentumDrift":
            window = min(len(returns), max(20, horizon * 3))
            mu = mean(returns[-window:])
        elif model == "MeanReversion":
            window = min(len(returns), max(20, horizon * 4))
            recent = mean(returns[-window:])
            long_term = mean(returns)
            mu = long_term + (long_term - recent) * 0.5
        else:
            raise ValueError(f"Unsupported forecast model: {model}")
        return mu * horizon

    @classmethod
    def _forecast_price(cls, candles: Sequence[Candle], model: str, horizon: int) -> float:
        current = candles[-1].close
        return current * exp(cls._predict_return(candles, model, horizon))

    @classmethod
    def _candidate_metrics(
        cls,
        train: Sequence[Candle],
        validation: Sequence[Candle],
        model: str,
        horizon: int,
    ) -> ForecastModelCandidate:
        if not validation:
            raise ValueError("Validation candles are required")
        errors: list[float] = []
        directions: list[float] = []
        max_start = len(validation) - horizon
        if max_start <= 0:
            max_start = 1
        for offset in range(max_start):
            prefix = list(train) + list(validation[:offset + 1])
            origin = prefix[-1].close
            target_index = min(offset + horizon, len(validation) - 1)
            actual = validation[target_index].close
            predicted = cls._forecast_price(prefix, model, horizon)
            if actual:
                errors.append(abs(predicted - actual) / actual * 100.0)
            predicted_direction = predicted >= origin
            actual_direction = actual >= origin
            directions.append(1.0 if predicted_direction == actual_direction else 0.0)
        anchor_price = validation[0].close
        expected_price = cls._forecast_price(list(train) + [validation[0]], model, horizon)
        expected_return_pct = (expected_price / anchor_price - 1.0) * 100.0 if anchor_price else 0.0
        mae = mean(errors) if errors else 100.0
        direction_accuracy = mean(directions) * 100.0 if directions else 0.0
        score = cls._score(mae, direction_accuracy)
        return ForecastModelCandidate(
            name=model,
            expected_price=expected_price,
            expected_return_pct=expected_return_pct,
            absolute_error_pct=mae,
            directional_accuracy_pct=direction_accuracy,
            score=score,
        )

    @staticmethod
    def _score(mae_pct: float, directional_accuracy_pct: float) -> float:
        error_score = max(0.0, min(100.0, 100.0 - mae_pct * 10.0))
        direction_score = max(0.0, min(100.0, directional_accuracy_pct))
        return round(error_score * 0.60 + direction_score * 0.40, 4)

    @classmethod
    def _select(
        cls,
        candles: Sequence[Candle],
        horizon: int,
    ) -> ForecastModelSelectionPoint:
        split = len(candles) - cls.HOLDOUT_SIZE
        if split < cls.MIN_TRAIN_SIZE:
            raise ValueError("Недостаточно истории для выбора прогнозной модели")
        train = list(candles[:split])
        validation = list(candles[split:])
        candidates = tuple(
            cls._candidate_metrics(train, validation, model, horizon)
            for model in cls.MODELS
        )
        selected = max(candidates, key=lambda item: (item.score, item.directional_accuracy_pct, -item.absolute_error_pct))
        return ForecastModelSelectionPoint(horizon, selected.name, selected.score, candidates)

    @classmethod
    def _build_selected_point(
        cls,
        candles: Sequence[Candle],
        horizon: int,
        selected_model: str,
        confidence: str,
    ) -> ForecastPoint:
        current_price = candles[-1].close
        returns = cls._returns(candles)
        mu = cls._predict_return(candles, selected_model, horizon) / horizon
        sigma = pstdev(returns) if len(returns) > 1 else 0.0
        return ForecastService._point(current_price, mu, sigma, horizon, confidence)

    @classmethod
    def select_and_forecast(
        cls,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        horizons: Sequence[int] = SUPPORTED_HORIZONS,
    ) -> AdaptiveForecastResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        if len(ordered) < cls.MIN_CANDLES:
            raise ValueError(f"Для выбора модели требуется не менее {cls.MIN_CANDLES} свечей")
        selections = tuple(cls._select(ordered, horizon) for horizon in sorted(set(horizons)))
        base = ForecastService.forecast(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=ordered,
            horizons=horizons,
        )
        points = tuple(
            cls._build_selected_point(
                ordered,
                selection.horizon_days,
                selection.selected_model,
                base.point(selection.horizon_days).confidence,
            )
            for selection in selections
        )
        forecast = ForecastResult(
            instrument_uid=base.instrument_uid,
            ticker=base.ticker,
            generated_at=base.generated_at,
            model="AdaptiveModelSelection",
            confidence=base.confidence,
            points=points,
            version=base.version,
        )
        return AdaptiveForecastResult(forecast=forecast, selections=selections)
