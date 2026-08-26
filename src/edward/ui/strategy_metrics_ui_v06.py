from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StrategyMetricsView:
    strategy_name: str | None
    quality_gate: str
    strategy_confidence: str
    forecast_confidence: str


def build_strategy_metrics_view(
    *,
    strategy_name: str | None,
    quality_gate: bool | None,
    strategy_confidence: str | None,
    forecast_confidence: str | None,
) -> StrategyMetricsView:
    """Build explicit UI labels for strategy and forecast quality metrics."""
    gate_label = "PASS" if quality_gate is True else "FAIL" if quality_gate is False else "N/A"
    strategy_label = str(strategy_confidence or "N/A") if quality_gate is True else "N/A"
    forecast_label = str(forecast_confidence or "N/A")
    return StrategyMetricsView(
        strategy_name=strategy_name,
        quality_gate=gate_label,
        strategy_confidence=strategy_label,
        forecast_confidence=forecast_label,
    )


def strategy_metrics_text(view: StrategyMetricsView) -> str:
    """Return a compact localized block suitable for Tkinter labels/text widgets."""
    strategy = view.strategy_name or "нет"
    return (
        f"Стратегия: {strategy}\n"
        f"Качество стратегии: {view.quality_gate}\n"
        f"Уверенность стратегии: {view.strategy_confidence}\n"
        f"Уверенность прогноза: {view.forecast_confidence}"
    )
