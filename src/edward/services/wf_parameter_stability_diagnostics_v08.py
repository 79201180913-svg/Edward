from __future__ import annotations

from statistics import mean
from typing import Any, Sequence

from edward.services.research_backtest_service_v08 import ResearchBacktestResult


def parameter_key(parameters: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(parameters.items()))


def winner_margin_pct(
    candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
) -> float:
    values = sorted((result.excess_return_pct for _, result in candidates), reverse=True)
    if len(values) < 2:
        return 100.0
    return max(0.0, min(100.0, (values[0] - values[1]) / max(abs(values[0]), 1.0) * 100.0))


def _distance(
    left: dict[str, Any],
    right: dict[str, Any],
    candidates: Sequence[dict[str, Any]],
) -> float:
    if left == right:
        return 0.0
    distances: list[float] = []
    for key in set(left) | set(right):
        lv, rv = left.get(key), right.get(key)
        if lv == rv:
            distances.append(0.0)
            continue
        values = [item[key] for item in candidates if key in item]
        numeric = values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values)
        if numeric and len(set(values)) > 1:
            ordered = sorted(set(float(value) for value in values))
            li = min(range(len(ordered)), key=lambda index: abs(ordered[index] - float(lv)))
            ri = min(range(len(ordered)), key=lambda index: abs(ordered[index] - float(rv)))
            distances.append(abs(li - ri) / (len(ordered) - 1))
        else:
            distances.append(1.0)
    return mean(distances) if distances else 1.0


def neighborhood_stability_pct(
    winner: dict[str, Any],
    candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
) -> tuple[float, int]:
    if len(candidates) <= 1:
        return 100.0, 0
    params = [item[0] for item in candidates]
    nearby = [
        result
        for candidate, result in candidates
        if candidate != winner and _distance(winner, candidate, params) <= 0.5
    ]
    if not nearby:
        return 0.0, 0
    winner_result = next(result for candidate, result in candidates if candidate == winner)
    winner_score = winner_result.excess_return_pct
    support = mean(result.excess_return_pct for result in nearby)
    if support >= winner_score:
        return 100.0, len(nearby)
    return max(0.0, min(100.0, support / max(abs(winner_score), 1.0) * 100.0)), len(nearby)


def selection_confidence(winner_margin: float, neighborhood_stability: float) -> float:
    return round((winner_margin + neighborhood_stability) / 2.0, 2)
