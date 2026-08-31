from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Sequence


@dataclass(frozen=True, slots=True)
class TradingPathEvidenceV088:
    temporal_block_count: int
    temporal_positive_blocks: int
    overlap_max_ratio: float
    multiple_testing_count: int
    multiple_testing_rank: int

    @property
    def temporal_stable(self) -> bool:
        return self.temporal_block_count > 0 and self.temporal_positive_blocks == self.temporal_block_count


class TradingPathEvidenceServiceV088:
    """Build conservative evidence from the already validated event returns."""

    @staticmethod
    def temporal_blocks(returns: Sequence[float], blocks: int = 3) -> tuple[float, ...]:
        values = tuple(float(value) for value in returns)
        if not values:
            return ()
        count = min(max(1, blocks), len(values))
        result: list[float] = []
        for index in range(count):
            start = index * len(values) // count
            end = (index + 1) * len(values) // count
            chunk = values[start:end]
            result.append(sum(chunk) / len(chunk) if chunk else 0.0)
        return tuple(result)

    @classmethod
    def build(cls, returns: Sequence[float], *, overlap_max_ratio: float = 0.0, multiple_testing_count: int = 1, multiple_testing_rank: int = 1) -> TradingPathEvidenceV088:
        blocks = cls.temporal_blocks(returns)
        positive = sum(1 for value in blocks if value > 0)
        return TradingPathEvidenceV088(
            temporal_block_count=len(blocks),
            temporal_positive_blocks=positive,
            overlap_max_ratio=max(0.0, min(1.0, float(overlap_max_ratio))),
            multiple_testing_count=max(1, int(multiple_testing_count)),
            multiple_testing_rank=max(1, int(multiple_testing_rank)),
        )


__all__ = ["TradingPathEvidenceV088", "TradingPathEvidenceServiceV088"]
