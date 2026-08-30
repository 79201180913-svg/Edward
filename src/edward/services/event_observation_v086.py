from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from edward.services.analysis_service import Candle
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryServiceV086
from edward.services.regime_engine_v08 import RegimeEngine


@dataclass(frozen=True, slots=True)
class EventObservationV086:
    hypothesis: str
    index: int
    timestamp: object
    regime: str
    volatility_bucket: str
    direction: str
    forward_returns_pct: tuple[tuple[int, float | None], ...]

    def forward_return(self, horizon: int) -> float | None:
        return dict(self.forward_returns_pct).get(horizon)


class EventObservationBuilderV086:
    """Build the canonical event annotations consumed by v0.8.6 research layers."""

    @classmethod
    def build(cls, candles: Sequence[Candle]) -> tuple[EventObservationV086, ...]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        observations: list[EventObservationV086] = []
        for hypothesis in ConditionalDiscoveryServiceV086.HYPOTHESES:
            for index in ConditionalDiscoveryServiceV086._event_indices(ordered, hypothesis):
                regime = RegimeEngine.classify(ordered[: index + 1]).regime
                volatility = ConditionalDiscoveryServiceV086._volatility_bucket(ordered, index)
                direction = ConditionalDiscoveryServiceV086._direction(ordered, index)
                forward = tuple(
                    (horizon, ConditionalDiscoveryServiceV086._forward_return(ordered, index, horizon))
                    for horizon in ConditionalDiscoveryServiceV086.HORIZONS
                )
                observations.append(
                    EventObservationV086(
                        hypothesis=hypothesis,
                        index=index,
                        timestamp=ordered[index].timestamp,
                        regime=regime,
                        volatility_bucket=volatility,
                        direction=direction,
                        forward_returns_pct=tuple(
                            (horizon, value * 100.0 if value is not None else None)
                            for horizon, value in forward
                        ),
                    )
                )
        return tuple(observations)


__all__ = ["EventObservationV086", "EventObservationBuilderV086"]
