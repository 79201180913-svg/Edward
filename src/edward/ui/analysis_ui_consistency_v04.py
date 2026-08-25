from __future__ import annotations

from dataclasses import replace
from typing import Any

from edward.services.analysis_service import AnalysisResult, AnalysisService, StrategyResult


def select_decision_strategy(result: AnalysisResult) -> tuple[AnalysisResult, StrategyResult | None, bool]:
    """Align the UI-selected strategy with the strategy actually used by Decision Engine."""
    if not result.strategies:
        return result, None, False

    passing = [item for item in result.strategies if item.quality_gate]
    selected = max(passing or result.strategies, key=lambda item: item.score)
    fallback = not bool(passing)

    ordered = [selected] + [item for item in result.strategies if item is not selected]
    recommendation = selected.strategy
    if fallback:
        recommendation = f"{selected.strategy} (fallback: Quality Gate FAIL)"

    normalized = replace(
        result,
        strategies=ordered,
        recommendation=recommendation,
        score=selected.score,
    )
    return normalized, selected, fallback


def install_analysis_ui_consistency() -> None:
    """Normalize AnalysisResult before the v0.4 analysis UI consumes it."""
    if getattr(AnalysisService, "_v04_ui_consistency_installed", False):
        return

    original_analyze = AnalysisService.analyze

    def analyze(self: AnalysisService, *args: Any, **kwargs: Any) -> AnalysisResult:
        result = original_analyze(self, *args, **kwargs)
        normalized, _, _ = select_decision_strategy(result)
        return normalized

    AnalysisService.analyze = analyze  # type: ignore[method-assign]
    AnalysisService._v04_ui_consistency_installed = True
