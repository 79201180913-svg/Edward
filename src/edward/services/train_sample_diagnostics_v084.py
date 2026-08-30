from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from edward.services.train_activity_diagnostics_v084 import TrainActivityDiagnosticsServiceV084


@dataclass(frozen=True, slots=True)
class TrainSampleDiagnosticsV084:
    windows: int
    no_trades_windows: int
    low_sample_windows: int
    adequate_sample_windows: int
    mean_selected_train_trades: float
    min_selected_train_trades: int
    max_selected_train_trades: int
    low_sample_pct: float


class TrainSampleDiagnosticsServiceV084:
    """Aggregate selected Train trade counts without changing selection."""

    @staticmethod
    def evaluate(trade_counts: Sequence[int], *, adequate_min_trades: int = 5) -> TrainSampleDiagnosticsV084:
        classified = [
            TrainActivityDiagnosticsServiceV084.classify_trade_count(trades, adequate_min_trades=adequate_min_trades)
            for trades in trade_counts
        ]
        trades = [item.trades for item in classified]
        no_trades = sum(item.classification == TrainActivityDiagnosticsServiceV084.NO_TRADES for item in classified)
        low_sample = sum(item.classification == TrainActivityDiagnosticsServiceV084.LOW_SAMPLE for item in classified)
        adequate = sum(item.classification == TrainActivityDiagnosticsServiceV084.ADEQUATE_SAMPLE for item in classified)
        return TrainSampleDiagnosticsV084(
            windows=len(classified),
            no_trades_windows=no_trades,
            low_sample_windows=low_sample,
            adequate_sample_windows=adequate,
            mean_selected_train_trades=round(mean(trades), 8) if trades else 0.0,
            min_selected_train_trades=min(trades) if trades else 0,
            max_selected_train_trades=max(trades) if trades else 0,
            low_sample_pct=round(low_sample / len(classified) * 100.0, 4) if classified else 0.0,
        )


__all__ = ["TrainSampleDiagnosticsV084", "TrainSampleDiagnosticsServiceV084"]
