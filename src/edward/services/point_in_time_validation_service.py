from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.forecast_service import ForecastService
from edward.services.forecast_model_selection_service import ForecastModelSelectionService
from edward.services.forecast_walk_forward_service import ForecastWalkForwardService


PIT_VALIDATION_VERSION = "0.5.0"


@dataclass(frozen=True, slots=True)
class PointInTimeValidationResult:
    passed: bool
    checked_layers: tuple[str, ...]
    failures: tuple[str, ...]
    version: str = PIT_VALIDATION_VERSION


class PointInTimeValidationService:
    """Validate that forecast layers do not depend on data after the origin."""

    @staticmethod
    def _same_forecast(a, b) -> bool:
        if a.model != b.model or a.confidence != b.confidence or len(a.points) != len(b.points):
            return False
        return all(x == y for x, y in zip(a.points, b.points))

    @classmethod
    def validate_forecast(cls, candles: Sequence[Candle], *, future_candles: Sequence[Candle] | None = None) -> bool:
        base = ForecastService.forecast(instrument_uid="pit", ticker="PIT", candles=candles)
        if future_candles is None:
            return True
        extended = ForecastService.forecast(instrument_uid="pit", ticker="PIT", candles=list(candles) + list(future_candles))
        return cls._same_forecast(base, extended)

    @classmethod
    def validate_model_selection(cls, candles: Sequence[Candle], *, future_candles: Sequence[Candle]) -> bool:
        base = ForecastModelSelectionService.select(candles=candles, horizons=(1, 5, 20, 60))
        extended = ForecastModelSelectionService.select(candles=list(candles) + list(future_candles), horizons=(1, 5, 20, 60))
        if set(base) != set(extended):
            return False
        return all(base[h].model == extended[h].model for h in base)

    @classmethod
    def validate_walk_forward(cls, candles: Sequence[Candle], *, future_candles: Sequence[Candle]) -> bool:
        base = ForecastWalkForwardService.validate(candles=candles, horizon=5)
        extended = ForecastWalkForwardService.validate(candles=list(candles) + list(future_candles), horizon=5)
        return bool(base.windows) and base.windows[0] == extended.windows[0]

    @classmethod
    def validate_all(cls, candles: Sequence[Candle], *, future_candles: Sequence[Candle]) -> PointInTimeValidationResult:
        checked: list[str] = []
        failures: list[str] = []
        for name, fn in (
            ("forecast", cls.validate_forecast),
            ("model_selection", cls.validate_model_selection),
            ("walk_forward", cls.validate_walk_forward),
        ):
            checked.append(name)
            try:
                if not fn(candles, future_candles=future_candles):
                    failures.append(f"{name.upper()}_LOOKAHEAD_DETECTED")
            except Exception as exc:
                failures.append(f"{name.upper()}_VALIDATION_ERROR:{type(exc).__name__}")
        return PointInTimeValidationResult(not failures, tuple(checked), tuple(failures))
