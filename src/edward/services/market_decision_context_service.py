from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from edward.services.analysis_service import Candle
from edward.services.decision_engine import MarketContextData


@dataclass(frozen=True, slots=True)
class MarketDecisionContextService:
    """Build Market Context from T-Invest market-data payloads."""

    def build(
        self,
        *,
        last_price: Any | None = None,
        close_price: Any | None = None,
        candles: Iterable[Any] = (),
        market_regime: str | None = None,
        trend: str | None = None,
        momentum: str | None = None,
        volatility: float | None = None,
        entry_level: float | None = None,
        stop_level: float | None = None,
        target_level: float | None = None,
        regime_compatible: bool = True,
        entry_ok: bool = False,
    ) -> MarketContextData:
        return MarketContextData(
            current_price=_quotation_to_float(last_price),
            close_price=_quotation_to_float(close_price),
            market_regime=market_regime,
            trend=trend,
            momentum=momentum,
            volatility=volatility,
            entry_level=entry_level,
            stop_level=stop_level,
            target_level=target_level,
            regime_compatible=bool(regime_compatible),
            entry_ok=bool(entry_ok),
            available=last_price is not None or close_price is not None or bool(list(candles)),
        )

    def candles(self, payload: Any) -> list[Candle]:
        """Normalize T-Invest HistoricCandle payloads to Edward Candle objects."""
        items = payload if isinstance(payload, list) else _field(payload, "candles", []) or []
        result: list[Candle] = []
        for item in items:
            timestamp = _field(item, "time")
            if timestamp is None:
                continue
            result.append(
                Candle(
                    timestamp=timestamp,
                    open=_quotation_to_float(_field(item, "open")) or 0.0,
                    high=_quotation_to_float(_field(item, "high")) or 0.0,
                    low=_quotation_to_float(_field(item, "low")) or 0.0,
                    close=_quotation_to_float(_field(item, "close")) or 0.0,
                    volume=float(_field(item, "volume", 0.0) or 0.0),
                )
            )
        return result


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _quotation_to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    units = _field(value, "units")
    nano = _field(value, "nano")
    if units is None and nano is None:
        return None
    try:
        return float(units or 0) + float(nano or 0) / 1_000_000_000
    except (TypeError, ValueError):
        return None
