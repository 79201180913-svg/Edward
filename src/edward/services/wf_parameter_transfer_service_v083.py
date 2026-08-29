from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Sequence

from edward.services.research_backtest_service_v08 import ResearchBacktestResult
from edward.services.wf_parameter_stability_diagnostics_v08 import neighborhood_stability_pct, parameter_key

WF_PARAMETER_TRANSFER_V083_VERSION = "0.8.3"
logger = logging.getLogger(__name__)


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
    historical_mean_return_pct: float = 0.0
    historical_median_return_pct: float = 0.0
    historical_mean_sharpe: float = 0.0
    historical_mean_drawdown_pct: float = 0.0
    historical_positive_pct: float = 0.0


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
    """Train-only shadow selector with historical WF transfer evidence.

    Current-window Train results are the only current-window inputs. Historical
    evidence must come from windows that completed before the current window.
    Current-window OOS data is deliberately absent from this API, preventing
    look-ahead leakage.
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
    def _percentile(value: float, values: Sequence[float], *, higher_is_better: bool = True) -> float:
        ordered = sorted(set(values), reverse=not higher_is_better)
        if len(ordered) <= 1:
            return 100.0
        index = ordered.index(value)
        return index / (len(ordered) - 1) * 100.0

    @classmethod
    def _historical_statistics(
        cls,
        entries: Sequence[ParameterTransferHistoryEntry],
    ) -> tuple[float, float, float, float, float]:
        if not entries:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        returns = [entry.oos_net_return_pct for entry in entries]
        sharpes = [entry.oos_sharpe for entry in entries]
        drawdowns = [entry.oos_drawdown_pct for entry in entries]
        positive_pct = sum(value > 0.0 for value in returns) / len(returns) * 100.0
        return mean(returns), median(returns), mean(sharpes), mean(drawdowns), positive_pct

    @classmethod
    def _historical_score(
        cls,
        entries: Sequence[ParameterTransferHistoryEntry],
        all_history: Sequence[ParameterTransferHistoryEntry],
    ) -> tuple[float, int]:
        if not entries:
            return 0.0, 0
        if not all_history:
            return 0.0, len(entries)

        returns = [entry.oos_net_return_pct for entry in all_history]
        sharpes = [entry.oos_sharpe for entry in all_history]
        drawdowns = [entry.oos_drawdown_pct for entry in all_history]
        return_score = mean(cls._percentile(entry.oos_net_return_pct, returns) for entry in entries)
        sharpe_score = mean(cls._percentile(entry.oos_sharpe, sharpes) for entry in entries)
        dd_score = mean(cls._percentile(entry.oos_drawdown_pct, drawdowns, higher_is_better=False) for entry in entries)
        confidence_score = mean(max(0.0, min(100.0, entry.selection_confidence)) for entry in entries)
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
            historical_entries = history_by_key.get(key, ())
            historical_score, support = cls._historical_score(historical_entries, history)
            historical_mean_return, historical_median_return, historical_mean_sharpe, historical_mean_drawdown, historical_positive_pct = cls._historical_statistics(historical_entries)
            if support >= cls.MIN_HISTORICAL_SUPPORT:
                score = current_score * cls.CURRENT_WEIGHT + historical_score * cls.HISTORICAL_WEIGHT
            else:
                score = current_score
            row = ParameterTransferCandidate(
                parameters=dict(params),
                consensus_score=round(consensus, 4),
                neighborhood_stability_pct=round(neighborhood, 4),
                historical_score=round(historical_score, 4),
                historical_support=support,
                selection_score=round(score, 4),
                historical_mean_return_pct=round(historical_mean_return, 4),
                historical_median_return_pct=round(historical_median_return, 4),
                historical_mean_sharpe=round(historical_mean_sharpe, 4),
                historical_mean_drawdown_pct=round(historical_mean_drawdown, 4),
                historical_positive_pct=round(historical_positive_pct, 4),
            )
            candidate_rows.append(row)
            logger.warning(
                "[V083 WF TRANSFER CANDIDATE] params=%s current_score=%.4f historical_score=%.4f support=%d historical_mean_return=%.4f historical_median_return=%.4f historical_mean_sharpe=%.4f historical_mean_dd=%.4f historical_positive_pct=%.2f selection_score=%.4f eligible=%s",
                params,
                current_score,
                row.historical_score,
                row.historical_support,
                row.historical_mean_return_pct,
                row.historical_median_return_pct,
                row.historical_mean_sharpe,
                row.historical_mean_drawdown_pct,
                row.historical_positive_pct,
                row.selection_score,
                support >= cls.MIN_HISTORICAL_SUPPORT,
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
        logger.warning(
            "[V083 WF TRANSFER SELECTION] baseline=%s selected=%s changed=%s history_windows=%d baseline_score=%.4f selected_score=%.4f selected_support=%d selected_historical_return=%.4f selected_historical_positive_pct=%.2f",
            baseline,
            selected.parameters,
            parameter_key(selected.parameters) != parameter_key(baseline),
            len(history),
            baseline_row.selection_score,
            selected.selection_score,
            selected.historical_support,
            selected.historical_mean_return_pct,
            selected.historical_positive_pct,
        )
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