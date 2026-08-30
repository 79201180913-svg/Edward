from __future__ import annotations

from dataclasses import dataclass

from edward.services.research_backtest_service_v08 import ResearchBacktestResult


@dataclass(frozen=True, slots=True)
class TrainActivityDiagnosticsV084:
    classification: str
    trades: int


class TrainActivityDiagnosticsServiceV084:
    NO_TRADES = "NO_TRADES"
    LOW_SAMPLE = "LOW_SAMPLE"
    ADEQUATE_SAMPLE = "ADEQUATE_SAMPLE"

    @classmethod
    def classify(cls, result: ResearchBacktestResult, *, adequate_min_trades: int = 5) -> TrainActivityDiagnosticsV084:
        trades = int(result.trades)
        if trades <= 0:
            classification = cls.NO_TRADES
        elif trades < adequate_min_trades:
            classification = cls.LOW_SAMPLE
        else:
            classification = cls.ADEQUATE_SAMPLE
        return TrainActivityDiagnosticsV084(classification=classification, trades=trades)


__all__ = ["TrainActivityDiagnosticsV084", "TrainActivityDiagnosticsServiceV084"]
