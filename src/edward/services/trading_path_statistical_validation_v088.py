from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class TemporalBlockEvidenceV088:
    block_index: int
    observations: int
    mean_return_pct: float


@dataclass(frozen=True, slots=True)
class TradingPathStatisticalEvidenceV088:
    observations: int
    mean_return_pct: float
    median_return_pct: float
    win_rate_pct: float
    std_return_pct: float
    standard_error_pct: float
    ci95_low_pct: float
    ci95_high_pct: float
    positive_mean: bool
    temporal_blocks: tuple[TemporalBlockEvidenceV088, ...]
    positive_temporal_blocks: int


class TradingPathStatisticalValidationV088:
    """Produce descriptive statistical and temporal evidence without promotion."""

    @staticmethod
    def _mean(values: Sequence[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @classmethod
    def evaluate(
        cls,
        returns_pct: Iterable[float],
        temporal_blocks: Sequence[Sequence[float]] = (),
    ) -> TradingPathStatisticalEvidenceV088:
        values = tuple(float(value) for value in returns_pct)
        n = len(values)
        mean = cls._mean(values)
        ordered = sorted(values)
        median = 0.0 if not ordered else (ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0)
        variance = sum((value - mean) ** 2 for value in values) / (n - 1) if n > 1 else 0.0
        std = sqrt(variance)
        se = std / sqrt(n) if n else 0.0
        blocks: list[TemporalBlockEvidenceV088] = []
        for index, block in enumerate(temporal_blocks):
            block_values = tuple(float(value) for value in block)
            block_mean = cls._mean(block_values)
            blocks.append(TemporalBlockEvidenceV088(index, len(block_values), block_mean))
        return TradingPathStatisticalEvidenceV088(
            observations=n,
            mean_return_pct=mean,
            median_return_pct=median,
            win_rate_pct=(sum(value > 0 for value in values) / n * 100.0) if n else 0.0,
            std_return_pct=std,
            standard_error_pct=se,
            ci95_low_pct=mean - 1.96 * se,
            ci95_high_pct=mean + 1.96 * se,
            positive_mean=mean > 0,
            temporal_blocks=tuple(blocks),
            positive_temporal_blocks=sum(block.mean_return_pct > 0 for block in blocks),
        )


__all__ = ["TemporalBlockEvidenceV088", "TradingPathStatisticalEvidenceV088", "TradingPathStatisticalValidationV088"]
