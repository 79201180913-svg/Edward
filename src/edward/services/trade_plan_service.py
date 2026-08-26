from __future__ import annotations

from dataclasses import dataclass

from edward.services.forecast_service import ForecastPoint


TRADE_PLAN_VERSION = "0.5.0"


@dataclass(frozen=True, slots=True)
class TradePlanInput:
    action: str
    forecast: ForecastPoint
    confidence: str
    holding_horizon_days: int
    entry_price: float | None = None
    position_weight_pct: float = 0.0
    target_weight_pct: float = 0.0
    max_position_weight_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class TradePlan:
    action: str
    entry_low: float | None
    entry_high: float | None
    target_price: float | None
    stop_price: float | None
    expected_return_pct: float
    expected_risk_pct: float
    risk_reward: float | None
    holding_horizon_days: int
    confidence: str
    version: str = TRADE_PLAN_VERSION


class TradePlanService:
    """Build a deterministic, execution-ready trade plan from forecast data."""

    ENTRY_BAND_FACTOR = 0.25
    STOP_BUFFER_FACTOR = 0.15

    @staticmethod
    def _action(action: str) -> str:
        normalized = str(action).upper().strip()
        allowed = {"BUY", "HOLD", "ADD", "REDUCE", "SELL"}
        if normalized not in allowed:
            raise ValueError(f"Неподдерживаемое действие Trade Plan: {action}")
        return normalized

    @classmethod
    def build(cls, data: TradePlanInput) -> TradePlan:
        action = cls._action(data.action)
        current = float(data.forecast.current_price)
        downside = float(data.forecast.downside_price)
        upside = float(data.forecast.upside_price)
        expected = float(data.forecast.expected_price)

        if current <= 0:
            raise ValueError("Текущая цена должна быть положительной")
        if data.holding_horizon_days <= 0:
            raise ValueError("Горизонт Trade Plan должен быть положительным")

        if action in {"BUY", "ADD"}:
            reference_entry = float(data.entry_price) if data.entry_price is not None else current
            risk_band = max(0.0, current - downside)
            entry_low = max(0.0, reference_entry - risk_band * cls.ENTRY_BAND_FACTOR)
            entry_high = reference_entry + risk_band * cls.ENTRY_BAND_FACTOR
            target = max(expected, upside)
            stop = max(0.0, downside - risk_band * cls.STOP_BUFFER_FACTOR)
        elif action in {"REDUCE", "SELL"}:
            reference_entry = float(data.entry_price) if data.entry_price is not None else current
            entry_low = entry_high = reference_entry
            target = downside
            stop = upside
        else:
            entry_low = entry_high = data.entry_price if data.entry_price is not None else current
            target = expected
            stop = downside

        expected_return = (target / current - 1.0) * 100.0 if target is not None else 0.0
        expected_risk = abs((current - stop) / current * 100.0) if stop is not None else 0.0
        risk_reward = expected_return / expected_risk if expected_risk > 0 else None

        return TradePlan(
            action=action,
            entry_low=round(entry_low, 8) if entry_low is not None else None,
            entry_high=round(entry_high, 8) if entry_high is not None else None,
            target_price=round(target, 8) if target is not None else None,
            stop_price=round(stop, 8) if stop is not None else None,
            expected_return_pct=round(expected_return, 4),
            expected_risk_pct=round(expected_risk, 4),
            risk_reward=round(risk_reward, 4) if risk_reward is not None else None,
            holding_horizon_days=int(data.holding_horizon_days),
            confidence=str(data.confidence),
        )
