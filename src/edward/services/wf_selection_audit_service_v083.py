from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class WFSelectionAuditWindow:
    """One completed WF window containing baseline, transfer and OOS oracle outcomes."""
    window_index: int
    baseline_parameters: Mapping[str, Any]
    transfer_parameters: Mapping[str, Any]
    baseline_oos_return_pct: float
    transfer_oos_return_pct: float
    oracle_parameters: Mapping[str, Any]
    oracle_oos_return_pct: float

    @property
    def transfer_delta_pct(self) -> float:
        return self.transfer_oos_return_pct - self.baseline_oos_return_pct

    @property
    def baseline_oracle_gap_pct(self) -> float:
        return self.oracle_oos_return_pct - self.baseline_oos_return_pct

    @property
    def transfer_oracle_gap_pct(self) -> float:
        return self.oracle_oos_return_pct - self.transfer_oos_return_pct

    @property
    def transfer_changed(self) -> bool:
        return dict(self.transfer_parameters) != dict(self.baseline_parameters)

    @property
    def transfer_won(self) -> bool:
        return self.transfer_oos_return_pct > self.baseline_oos_return_pct


@dataclass(frozen=True, slots=True)
class WFSelectionAuditResult:
    strategy: str
    windows: int
    changed_windows: int
    transfer_wins: int
    transfer_losses: int
    transfer_ties: int
    transfer_win_rate_pct: float
    mean_transfer_delta_pct: float
    median_transfer_delta_pct: float
    cumulative_baseline_return_pct: float
    cumulative_transfer_return_pct: float
    cumulative_oracle_return_pct: float
    mean_baseline_oracle_gap_pct: float
    mean_transfer_oracle_gap_pct: float


class WFSelectionAuditServiceV083:
    """Audit parameter selection without changing production selection or QG."""
    @staticmethod
    def _compound(values: Sequence[float]) -> float:
        value = 1.0
        for item in values:
            value *= 1.0 + item / 100.0
        return (value - 1.0) * 100.0

    @classmethod
    def evaluate(cls, strategy: str, windows: Iterable[WFSelectionAuditWindow]) -> WFSelectionAuditResult:
        items = tuple(windows)
        if not items:
            return WFSelectionAuditResult(strategy, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        changed = sum(item.transfer_changed for item in items)
        wins = sum(item.transfer_won and item.transfer_changed for item in items)
        losses = sum(item.transfer_delta_pct < 0.0 and item.transfer_changed for item in items)
        ties = changed - wins - losses
        deltas = [item.transfer_delta_pct for item in items if item.transfer_changed]
        baseline = [item.baseline_oos_return_pct for item in items]
        transfer = [item.transfer_oos_return_pct for item in items]
        oracle = [item.oracle_oos_return_pct for item in items]
        return WFSelectionAuditResult(
            strategy=strategy,
            windows=len(items),
            changed_windows=changed,
            transfer_wins=wins,
            transfer_losses=losses,
            transfer_ties=ties,
            transfer_win_rate_pct=wins / changed * 100.0 if changed else 0.0,
            mean_transfer_delta_pct=mean(deltas) if deltas else 0.0,
            median_transfer_delta_pct=median(deltas) if deltas else 0.0,
            cumulative_baseline_return_pct=cls._compound(baseline),
            cumulative_transfer_return_pct=cls._compound(transfer),
            cumulative_oracle_return_pct=cls._compound(oracle),
            mean_baseline_oracle_gap_pct=mean(item.baseline_oracle_gap_pct for item in items),
            mean_transfer_oracle_gap_pct=mean(item.transfer_oracle_gap_pct for item in items),
        )


__all__ = ["WFSelectionAuditWindow", "WFSelectionAuditResult", "WFSelectionAuditServiceV083"]
