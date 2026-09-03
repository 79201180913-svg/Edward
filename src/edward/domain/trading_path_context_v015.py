from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TradingPathContextV015:
    """Immutable context envelope preserved alongside canonical path analysis.

    The envelope intentionally keeps source payloads opaque: individual context
    producers remain responsible for their own schemas, while the canonical
    trading-path pipeline guarantees that these inputs are not silently dropped.
    """

    fundamentals: object | None = None
    instrument_metadata: object | None = None
    news: object | None = None
    news_overlay: object | None = None
    signals: object | None = None
    events: object | None = None
    dividends: object | None = None
    insider: object | None = None
    risk_metadata: object | None = None
    session: object | None = None


__all__ = ["TradingPathContextV015"]
