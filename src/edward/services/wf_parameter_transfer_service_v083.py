from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Sequence

from edward.services.research_backtest_service_v08 import ResearchBacktestResult
from edward.services.wf_parameter_stability_diagnostics_v08 import neighborhood_stability_pct, parameter_key

WF_PARAMETER_TRANSFER_V083_VERSION = "0.8.3"


@dataclass(frozen=True, slots=True)
class ParameterTransferCandidate:
    parameters: dict[str, Any]
    consensus_score: float
    neighborhood_stability_pct: float
    selection_score: float


@dataclass(frozen=True, slots=True)
class ParameterTransferSelection:
    selected_parameters: dict[str, Any]
    candidates: tuple[ParameterTransferCandidate, ...]
    baseline_parameters: dict[str, Any]
    baseline_score: float
    selected_score: float

    @property
    def changed_from_baseline(self) -> bool:
        return parameter_key(self.selected_parameters) != parameter_key(self.baseline_parameters)


class WFParameterTransferSelectorV083:
    """Train-only shadow selector for improving parameter transfer.

    The selector deliberately uses only Train results. OOS results are never
    used to choose parameters, preventing look-ahead leakage. It is intended
    to run in shadow mode first so the existing production selection remains
    unchanged while transfer quality is measured objectively.
    """

    CRITERIA = ("excess_return", "sharpe", "sortino", "return_dd")
    CONSENSUS_WEIGHT = 0.80
    NEIGHBORHOOD_WEIGHT = 0.20

    @staticmethod
    def _criterion_value(criterion: str, result: ResearchBacktestResult) -> float:
        if criterion == "excess_return":
            return result.excess_return_pct
        if criterion == "sharpe":
            return result.sharpe
        if criterion == "sortino":
            return result.sortino
        if criterion == "return_dd":
            return result.net_return_pct / max(result.max_drawdown_pct, 1e-9)
        raise ValueError(f"Unknown criterion: {criterion}")

    @classmethod
    def _criterion_percentiles(
        cls,
        candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
        criterion: str,
    ) -> dict[tuple[tuple[str, Any], ...], float]:
        values = [(parameter_key(params), cls._criterion_value(criterion, result)) for params, result in candidates]
        ordered = sorted(set(value for _, value in values))
        if len(ordered) <= 1:
            return {key: 100.0 for key, _ in values}
        return {
            key: (ordered.index(value) / (len(ordered) - 1)) * 100.0
            for key, value in values
        }

    @classmethod
    def select(
        cls,
        candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
        baseline_parameters: dict[str, Any] | None = None,
    ) -> ParameterTransferSelection:
        if not candidates:
            raise ValueError("candidates cannot be empty")

        baseline = dict(baseline_parameters or max(candidates, key=lambda item: item[1].excess_return_pct)[0])
        percentile_maps = {criterion: cls._criterion_percentiles(candidates, criterion) for criterion in cls.CRITERIA}
        candidate_rows: list[ParameterTransferCandidate] = []

        for params, _ in candidates:
            key = parameter_key(params)
            consensus = mean(percentile_maps[criterion][key] for criterion in cls.CRITERIA)
            neighborhood, _ = neighborhood_stability_pct(params, candidates)
            score = consensus * cls.CONSENSUS_WEIGHT + neighborhood * cls.NEIGHBORHOOD_WEIGHT
            candidate_rows.append(
                ParameterTransferCandidate(
                    parameters=dict(params),
                    consensus_score=round(consensus, 4),
                    neighborhood_stability_pct=round(neighborhood, 4),
                    selection_score=round(score, 4),
                )
            )

        ranked = sorted(
            candidate_rows,
            key=lambda item: (item.selection_score, item.consensus_score, item.neighborhood_stability_pct),
            reverse=True,
        )
        selected = ranked[0]
        baseline_row = next(row for row in candidate_rows if parameter_key(row.parameters) == parameter_key(baseline))
        return ParameterTransferSelection(
            selected_parameters=dict(selected.parameters),
            candidates=tuple(ranked),
            baseline_parameters=baseline,
            baseline_score=baseline_row.selection_score,
            selected_score=selected.selection_score,
        )


__all__ = [
    "WF_PARAMETER_TRANSFER_V083_VERSION",
    "ParameterTransferCandidate",
    "ParameterTransferSelection",
    "WFParameterTransferSelectorV083",
]
