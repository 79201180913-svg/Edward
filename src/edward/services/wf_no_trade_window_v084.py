from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NoTradeWindowV084:
    """A WF window where Train found no economically viable parameter."""

    index: int
    reason: str = "NO_VIABLE_TRAIN"
    active: bool = False
    test_return_pct: float = 0.0
    test_trades: int = 0


__all__ = ["NoTradeWindowV084"]
