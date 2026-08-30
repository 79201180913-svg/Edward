from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrainActivityDiagnosticsV084:
    classification: str
    trades: int


class TrainActivityDiagnosticsServiceV084:
    NO_TRADES = "NO_TRADES"
    LOW_SAMPLE = "LOW_SAMPLE"
    ADEQUATE_SAMPLE = "ADEQUATE_SAMPLE"

    @classmethod
    def classify_trade_count(cls, trades: int, *, adequate_min_trades: int = 5) -> TrainActivityDiagnosticsV084:
        count = int(trades)
        if count <= 0:
            classification = cls.NO_TRADES
        elif count < adequate_min_trades:
            classification = cls.LOW_SAMPLE
        else:
            classification = cls.ADEQUATE_SAMPLE
        return TrainActivityDiagnosticsV084(classification=classification, trades=count)

    @classmethod
    def classify(cls, result, *, adequate_min_trades: int = 5) -> TrainActivityDiagnosticsV084:
        return cls.classify_trade_count(result.trades, adequate_min_trades=adequate_min_trades)


__all__ = ["TrainActivityDiagnosticsV084", "TrainActivityDiagnosticsServiceV084"]
