from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import erf, exp, log, sqrt
from statistics import mean, pstdev
from typing import Iterable, Sequence

from edward.services.analysis_service import Candle


FORECAST_VERSION = "0.5.0"
SUPPORTED_HORIZONS = (1, 5, 20, 60)


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    horizon_days: int
    current_price: float
    expected_price: float
    expected_return_pct: float
    downside_price: float
    upside_price: float
    probability_up: float
    probability_down: float
    expected_volatility_pct: float
    expected_drawdown_pct: float
    confidence: str


@dataclass(frozen=True, slots=True)
class ForecastResult:
    instrument_uid: str
    ticker: str
    generated_at: str
    model: str
    confidence: str
    points: tuple[ForecastPoint, ...]
    version: str = FORECAST_VERSION

    def point(self, horizon_days: int) -> ForecastPoint:
        for item in self.points:
            if item.horizon_days == horizon_days:
                return item
        raise KeyError(f"Unsupported forecast horizon: {horizon_days}")


class ForecastService:
    """v0.5 statistical forecast engine.

    The method is point-in-time safe when ``origin_timestamp`` is supplied:
    candles after the origin are ignored before any calculation.
    """

    MODEL = "AdaptiveHistoricalDrift"
    MIN_CANDLES = 60

    @staticmethod
    def _log_returns(candles: Sequence[Candle]) -> list[float]:
        result: list[float] = []
        for previous, current in zip(candles, candles[1:]):
            if previous.close <= 0 or current.close <= 0:
                continue
            result.append(log(current.close / previous.close))
        return result

    @staticmethod
    def _normal_cdf(value: float) -> float:
        return 0.5 * (1.0 + erf(value / sqrt(2.0)))

    @classmethod
    def _confidence(cls, returns: Sequence[float], observations: int) -> str:
        if observations < 120 or len(returns) < 60:
            return "Low"
        if observations >= 500 and len(returns) >= 250:
            return "High"
        return "Medium"

    @classmethod
    def _point(cls, current_price: float, mu: float, sigma: float, horizon: int, confidence: str) -> ForecastPoint:
        drift = mu * horizon
        diffusion = sigma * sqrt(horizon)
        expected_price = current_price * exp(drift)
        downside_price = current_price * exp(drift - diffusion)
        upside_price = current_price * exp(drift + diffusion)
        expected_return_pct = (expected_price / current_price - 1.0) * 100.0
        expected_volatility_pct = (exp(diffusion) - 1.0) * 100.0
        probability_up = cls._normal_cdf(drift / diffusion) if diffusion > 0 else (1.0 if drift > 0 else 0.5)
        probability_down = 1.0 - probability_up
        expected_drawdown_pct = max(0.0, (current_price - downside_price) / current_price * 100.0)
        return ForecastPoint(
            horizon_days=horizon,
            current_price=current_price,
            expected_price=round(expected_price, 8),
            expected_return_pct=round(expected_return_pct, 4),
            downside_price=round(downside_price, 8),
            upside_price=round(upside_price, 8),
            probability_up=round(probability_up * 100.0, 4),
            probability_down=round(probability_down * 100.0, 4),
            expected_volatility_pct=round(expected_volatility_pct, 4),
            expected_drawdown_pct=round(expected_drawdown_pct, 4),
            confidence=confidence,
        )

    @staticmethod
    def _slice_to_origin(candles: Sequence[Candle], origin_timestamp) -> list[Candle]:
        if origin_timestamp is None:
            return list(candles)
        return [item for item in candles if item.timestamp <= origin_timestamp]

    @classmethod
    def forecast(
        cls,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        horizons: Sequence[int] = SUPPORTED_HORIZONS,
        origin_timestamp=None,
    ) -> ForecastResult:
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        ordered = cls._slice_to_origin(ordered, origin_timestamp)
        if len(ordered) < cls.MIN_CANDLES:
            raise ValueError(f"Для прогноза требуется не менее {cls.MIN_CANDLES} свечей")

        requested = tuple(sorted({int(item) for item in horizons if int(item) > 0}))
        unsupported = [item for item in requested if item not in SUPPORTED_HORIZONS]
        if unsupported:
            raise ValueError(f"Неподдерживаемые горизонты прогноза: {unsupported}")
        if not requested:
            raise ValueError("Не задан горизонт прогноза")

        current_price = float(ordered[-1].close)
        returns = cls._log_returns(ordered)
        if not returns:
            raise ValueError("Недостаточно корректных цен для прогноза")

        mu = mean(returns)
        sigma = pstdev(returns) if len(returns) > 1 else 0.0
        confidence = cls._confidence(returns, len(ordered))
        points = tuple(cls._point(current_price, mu, sigma, horizon, confidence) for horizon in requested)

        generated_at = datetime.now().astimezone().isoformat()
        return ForecastResult(
            instrument_uid=str(instrument_uid),
            ticker=str(ticker),
            generated_at=generated_at,
            model=cls.MODEL,
            confidence=confidence,
            points=points,
        )
