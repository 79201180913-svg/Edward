from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Sequence

from edward.services.research_backtest_service_v08 import ResearchBacktestResult
from edward.services.wf_parameter_stability_diagnostics_v08 import neighborhood_stability_pct, parameter_key

WF_PARAMETER_TRANSFER_V083_VERSION = "0.8.3"


@dataclass(frozen=True, slots=True)
class ParameterTransferHistoryEntry:
    """Previously completed WF window evidence available before the current window."""

    window_index: int
    parameters: dict[str, Any]
    oos_net_return_pct: float
    oos_sharpe: float
    oos_drawdown_pct: float
    selection_confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class ParameterTransferCandidate:
    parameters: dict[str, Any]
    consensus_score: float
    neighborhood_stability_pct: float
    historical_score: float
    historical_support: int
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
    """Train-only shadow selector with optional historical WF transfer evidence.

    Current-window Train results are the only current-window inputs. Historical
    evidence must come from windows that completed before the current window.
    OOS data from the current window is deliberately absent from this API so
    the selector cannot use look-ahead information to choose parameters.
    """

    CRITERIA = ("excess_return", "sharpe", "sortino", "return_dd")
    CONSENSUS_WEIGHT = 0.80
    NEIGHBORHOOD_WEIGHT = 0.20
    HISTORICAL_WEIGHT = 0.35
    CURRENT_WEIGHT = 0.65
    MIN_HISTORICAL_SUPPORT = 2

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
        return {key: (ordered.index(value) / (len(ordered) - 1)) * 100.0 for key, value in values}

    @staticmethod
    def _historical_score(entries: Sequence[ParameterTransferHistoryEntry]) -> tuple[float, int]:
        if not entries:
            return 0.0, 0

        returns = [entry.oos_net_return_pct for entry in entries]
        sharpes = [entry.oos_sharpe for entry in entries]
        drawdowns = [entry.oos_drawdown_pct for entry in entries]
        confidences = [max(0.0, min(100.0, entry.selection_confidence)) for entry in entries]

        def percentile(value: float, values: list[float], reverse: bool = False) -> float:
            ordered = sorted(set(values), reverse=reverse)
            if len(ordered) <= 1:
                return 100.0
            index = ordered.index(value)
            return index / (len(ordered) - 1) * 100.0

        return_score = mean(percentile(value, returns) for value in returns)
        sharpe_score = mean(percentile(value, sharpes) for value in sharpes)
        dd_score = mean(percentile(value, drawdowns, reverse=True) for value in drawdowns)
        confidence_score = mean(confidences)
        score = return_score * 0.35 + sharpe_score * 0.30 + dd_score * 0.20 + confidence_score * 0.15
        return round(score, 4), len(entries)

    @classmethod
    def select(
        cls,
        candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
        baseline_parameters: dict[str, Any] | None = None,
    ) -> ParameterTransferSelection:
        return cls._select(candidates, baseline_parameters=baseline_parameters, history=())

    @classmethod
    def select_with_history(
        cls,
        candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
        *,
        history: Sequence[ParameterTransferHistoryEntry],
        baseline_parameters: dict[str, Any] | None = None,
    ) -> ParameterTransferSelection:
        """Select from current Train candidates using only prior-window evidence."""
        return cls._select(candidates, baseline_parameters=baseline_parameters, history=history)

    @classmethod
    def _select(
        cls,
        candidates: Sequence[tuple[dict[str, Any], ResearchBacktestResult]],
        *,
        baseline_parameters: dict[str, Any] | None,
        history: Sequence[ParameterTransferHistoryEntry],
    ) -> ParameterTransferSelection:
        if not candidates:
            raise ValueError("candidates cannot be empty")

        baseline = dict(baseline_parameters or max(candidates, key=lambda item: item[1].excess_return_pct)[0])
        percentile_maps = {criterion: cls._criterion_percentiles(candidates, criterion) for criterion in cls.CRITERIA}
        history_by_key: dict[tuple[tuple[str, Any], ...], list[ParameterTransferHistoryEntry]] = {}
        for entry in history:
            history_by_key.setdefault(parameter_key(entry.parameters), []).append(entry)

        candidate_rows: list[ParameterTransferCandidate] = []
        for params, _ in candidates:
            key = parameter_key(params)
            consensus = mean(percentile_maps[criterion][key] for criterion in cls.CRITERIA)
            neighborhood, _ = neighborhood_stability_pct(params, candidates)
            current_score = consensus * cls.CONSENSUS_WEIGHT + neighborhood * cls.NEIGHBORHOOD_WEIGHT
            historical_score, support = cls._historical_score(history_by_key.get(key, ()))
            if support >= cls.MIN_HISTORICAL_SUPPORT:
                score = current_score * cls.CURRENT_WEIGHT + historical_score * cls.HISTORICAL_WEIGHT
            else:
                score = current_score
            candidate_rows.append(
                ParameterTransferCandidate(
                    parameters=dict(params),
                    consensus_score=round(consensus, 4),
                    neighborhood_stability_pct=round(neighborhood, 4),
                    historical_score=round(historical_score, 4),
                    historical_support=support,
                    selection_score=round(score, 4),
                )
            )

        ranked = sorted(
            candidate_rows,
            key=lambda item: (
                item.selection_score,
                item.historical_support,
                item.consensus_score,
                item.neighborhood_stability_pct,
                tuple(sorted(item.parameters.items())),
            ),
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
    "ParameterTransferHistoryEntry",
    "ParameterTransferCandidate",
    "ParameterTransferSelection",
    "WFParameterTransferSelectorV083",
]
