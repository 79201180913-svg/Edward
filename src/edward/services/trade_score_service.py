from __future__ import annotations

from dataclasses import dataclass


TRADE_SCORE_VERSION = "0.5.0"


@dataclass(frozen=True, slots=True)
class TradeScoreInput:
    strategy_score: float
    forecast_score: float
    risk_score: float
    opportunity_score: float
    portfolio_fit_score: float
    confidence_score: float
    forecast_quality_pass: bool = True


@dataclass(frozen=True, slots=True)
class TradeScoreResult:
    score: float
    strategy_component: float
    forecast_component: float
    risk_component: float
    opportunity_component: float
    portfolio_fit_component: float
    confidence_component: float
    forecast_used: bool
    blocked: bool
    reasons: tuple[str, ...]
    version: str = TRADE_SCORE_VERSION


class TradeScoreService:
    """v0.5 unified trading score.

    Forecast is a confirming factor only when its quality gate passes. When the
    forecast gate fails, the forecast component is removed rather than silently
    treated as a weak score, and the result is marked blocked for forecast-based
    trading decisions.
    """

    DEFAULT_WEIGHTS = {
        "strategy": 0.20,
        "forecast": 0.25,
        "risk": 0.20,
        "opportunity": 0.15,
        "portfolio_fit": 0.10,
        "confidence": 0.10,
    }

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @classmethod
    def calculate(
        cls,
        data: TradeScoreInput,
        *,
        weights: dict[str, float] | None = None,
    ) -> TradeScoreResult:
        selected = dict(cls.DEFAULT_WEIGHTS)
        if weights:
            selected.update(weights)
        if any(value < 0 for value in selected.values()):
            raise ValueError("Вес Trade Score не может быть отрицательным")

        total = sum(selected.values())
        if total <= 0:
            raise ValueError("Сумма весов Trade Score должна быть положительной")
        selected = {key: value / total for key, value in selected.items()}

        strategy = cls._clamp(data.strategy_score)
        forecast = cls._clamp(data.forecast_score)
        risk = cls._clamp(data.risk_score)
        opportunity = cls._clamp(data.opportunity_score)
        portfolio_fit = cls._clamp(data.portfolio_fit_score)
        confidence = cls._clamp(data.confidence_score)

        forecast_used = bool(data.forecast_quality_pass)
        blocked = False
        reasons: list[str] = []
        if not forecast_used:
            forecast = 0.0
            blocked = True
            reasons.append("FORECAST_QUALITY_GATE_FAIL")

        score = (
            strategy * selected["strategy"]
            + forecast * selected["forecast"]
            + risk * selected["risk"]
            + opportunity * selected["opportunity"]
            + portfolio_fit * selected["portfolio_fit"]
            + confidence * selected["confidence"]
        )

        return TradeScoreResult(
            score=round(cls._clamp(score), 4),
            strategy_component=round(strategy * selected["strategy"], 4),
            forecast_component=round(forecast * selected["forecast"], 4),
            risk_component=round(risk * selected["risk"], 4),
            opportunity_component=round(opportunity * selected["opportunity"], 4),
            portfolio_fit_component=round(portfolio_fit * selected["portfolio_fit"], 4),
            confidence_component=round(confidence * selected["confidence"], 4),
            forecast_used=forecast_used,
            blocked=blocked,
            reasons=tuple(reasons),
        )
