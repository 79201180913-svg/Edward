from __future__ import annotations

from typing import Any


def quality_gate_reasons(strategy_result: Any, profile_params: dict[str, Any]) -> list[tuple[bool, str]]:
    """Return transparent component-level checks for the beta Quality Gate."""
    return [
        (strategy_result.wf_windows >= 5, f"WF windows: {strategy_result.wf_windows} >= 5"),
        (strategy_result.return_consistency >= 60.0, f"Return consistency: {strategy_result.return_consistency:.0f}% >= 60%"),
        (strategy_result.stability >= profile_params["min_stability_pct"], f"Stability: {strategy_result.stability:.0f}% >= {profile_params['min_stability_pct']:.0f}%"),
        (strategy_result.return_pct > 0.0, f"Return: {strategy_result.return_pct:.2f}% > 0"),
        (strategy_result.max_drawdown_pct <= profile_params["max_drawdown_pct"], f"Max DD: {strategy_result.max_drawdown_pct:.2f}% <= {profile_params['max_drawdown_pct']:.0f}%"),
        (strategy_result.sharpe > 0.0, f"Sharpe: {strategy_result.sharpe:.2f} > 0"),
    ]
