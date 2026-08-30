from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Sequence

from edward.services.research_backtest_service_v08 import ResearchBacktestResult
from edward.services.wf_parameter_stability_diagnostics_v08 import neighborhood_stability_pct, parameter_key

logger = logging.getLogger(__name__)
PARAMETER_ZONE_V084_VERSION = "0.8.4"


@dataclass(frozen=True, slots=True)
class ParameterZoneV084:
    strategy: str
    candidates: int
    viable_candidates: int
    representative_parameters: dict[str, Any]
    parameter_keys: tuple[tuple[tuple[str, Any], ...], ...]
    mean_score: float
    median_score: float
    score_dispersion: float
    viability_pct: float
    neighborhood_stability_pct: float
    stable: bool


class ParameterZoneServiceV084:
    """Identify a stable parameter neighborhood using Train evidence only."""

    @staticmethod
    def _score(result: ResearchBacktestResult) -> float:
        return float(result.excess_return_pct)

    @classmethod
    def evaluate(
        cls,
        *,
        strategy: str,
        candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
        viable: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
    ) -> ParameterZoneV084:
        logger.warning("[V084 PARAMETER ZONE START] strategy=%s candidates=%d viable=%d", strategy, len(candidates), len(viable))
        if not viable:
            output = ParameterZoneV084(strategy, len(candidates), 0, {}, (), 0.0, 0.0, 0.0, 0.0, 0.0, False)
            logger.warning("[V084 PARAMETER ZONE RESULT] strategy=%s stable=False reason=no_viable_candidates", strategy)
            return output

        ranked = sorted(viable, key=lambda item: cls._score(item[1]), reverse=True)
        representative, representative_result = ranked[0]
        scores = [cls._score(item[1]) for item in ranked]
        mean_score = sum(scores) / len(scores)
        ordered = sorted(scores)
        middle = len(ordered) // 2
        median_score = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        dispersion = variance ** 0.5
        neighborhood, _ = neighborhood_stability_pct(representative, viable)
        viability_pct = len(viable) / len(candidates) * 100.0 if candidates else 0.0
        stable = len(viable) >= 2 and neighborhood >= 50.0
        output = ParameterZoneV084(
            strategy=strategy,
            candidates=len(candidates),
            viable_candidates=len(viable),
            representative_parameters=dict(representative),
            parameter_keys=tuple(parameter_key(params) for params, _ in ranked),
            mean_score=round(mean_score, 8),
            median_score=round(median_score, 8),
            score_dispersion=round(dispersion, 8),
            viability_pct=round(viability_pct, 4),
            neighborhood_stability_pct=round(neighborhood, 4),
            stable=stable,
        )
        for rank, (params, result) in enumerate(ranked, 1):
            logger.warning("[V084 PARAMETER ZONE CANDIDATE] strategy=%s rank=%d representative=%s params=%s train_excess=%.6f neighborhood=%.2f", strategy, rank, params == representative, params, result.excess_return_pct, neighborhood_stability_pct(params, viable)[0])
        logger.warning("[V084 PARAMETER ZONE RESULT] strategy=%s stable=%s representative=%s viable=%d/%d viability_pct=%.2f mean=%.6f median=%.6f dispersion=%.6f neighborhood=%.2f", strategy, stable, representative, len(viable), len(candidates), viability_pct, mean_score, median_score, dispersion, neighborhood)
        return output


__all__ = ["PARAMETER_ZONE_V084_VERSION", "ParameterZoneV084", "ParameterZoneServiceV084"]