from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import mean, median
from typing import Callable, Sequence

from edward.services.analysis_service import Candle


logger = logging.getLogger(__name__)
RESEARCH_DISCOVERY_VERSION = "0.8.5"


@dataclass(frozen=True, slots=True)
class DiscoveryHorizonEvidence:
    horizon: int
    observations: int
    mean_forward_return_pct: float
    median_forward_return_pct: float
    win_rate_pct: float
    baseline_mean_return_pct: float
    excess_return_pct: float


@dataclass(frozen=True, slots=True)
class DiscoveryEvidence:
    hypothesis: str
    description: str
    events: int
    first_event: object | None
    last_event: object | None
    horizons: tuple[DiscoveryHorizonEvidence, ...]

    @property
    def strongest_horizon(self) -> DiscoveryHorizonEvidence | None:
        return max(self.horizons, key=lambda item: item.excess_return_pct, default=None)


@dataclass(frozen=True, slots=True)
class ResearchDiscoveryResult:
    version: str
    candles: int
    baseline_horizons: tuple[DiscoveryHorizonEvidence, ...]
    hypotheses: tuple[DiscoveryEvidence, ...]


class ResearchDiscoveryServiceV085:
    """Discovery-only event study for finding tradeable structure.

    This service does not select parameters, alter Quality Gate rules, or create
    a trading recommendation. It asks a narrower research question: when a
    predefined market event occurs, is subsequent price behaviour different
    from the unconditional baseline?
    """

    HORIZONS = (1, 3, 5, 10, 20)
    MIN_LOOKBACK = 20

    @staticmethod
    def _returns(candles: Sequence[Candle]) -> list[float]:
        return [
            float(current.close) / float(previous.close) - 1.0
            for previous, current in zip(candles, candles[1:])
            if float(previous.close) > 0 and float(current.close) > 0
        ]

    @staticmethod
    def _forward_return(candles: Sequence[Candle], index: int, horizon: int) -> float | None:
        end = index + horizon
        if index < 0 or end >= len(candles):
            return None
        start_price = float(candles[index].close)
        end_price = float(candles[end].close)
        if start_price <= 0 or end_price <= 0:
            return None
        return end_price / start_price - 1.0

    @classmethod
    def _baseline(cls, candles: Sequence[Candle], horizon: int) -> list[float]:
        values = [cls._forward_return(candles, index, horizon) for index in range(len(candles))]
        return [value for value in values if value is not None]

    @classmethod
    def _event_indices(cls, candles: Sequence[Candle], hypothesis: str) -> list[int]:
        closes = [float(item.close) for item in candles]
        opens = [float(item.open) for item in candles]
        highs = [float(item.high) for item in candles]
        lows = [float(item.low) for item in candles]
        indices: list[int] = []

        for index in range(cls.MIN_LOOKBACK, len(candles)):
            window = closes[index - 20:index]
            if len(window) < 20 or closes[index] <= 0:
                continue

            if hypothesis == "BREAKOUT_EXPANSION":
                prior_high = max(highs[index - 20:index])
                true_ranges = [max(highs[j] - lows[j], abs(highs[j] - closes[j - 1]), abs(lows[j] - closes[j - 1])) for j in range(index - 20, index) if closes[j - 1] > 0]
                current_tr = max(highs[index] - lows[index], abs(highs[index] - closes[index - 1]), abs(lows[index] - closes[index - 1]))
                if true_ranges and current_tr >= median(true_ranges) * 1.5 and closes[index] >= prior_high:
                    indices.append(index)

            elif hypothesis == "PULLBACK_RECLAIM":
                fast = mean(closes[index - 10:index])
                slow = mean(closes[index - 30:index]) if index >= 30 else mean(closes[index - 20:index])
                previous_fast = mean(closes[index - 11:index - 1])
                if fast > slow and closes[index - 1] <= previous_fast and closes[index] > fast:
                    indices.append(index)

            elif hypothesis == "IMPULSE_CONTINUATION":
                impulse = closes[index - 3] / closes[index - 8] - 1.0 if index >= 8 and closes[index - 8] > 0 else 0.0
                if impulse >= 0.05 and closes[index] > closes[index - 1]:
                    indices.append(index)

            elif hypothesis == "SHOCK_REVERSAL":
                one_bar = closes[index] / closes[index - 1] - 1.0 if closes[index - 1] > 0 else 0.0
                if one_bar <= -0.04:
                    indices.append(index)

            elif hypothesis == "GAP_REVERSAL":
                gap = opens[index] / closes[index - 1] - 1.0 if closes[index - 1] > 0 else 0.0
                if gap <= -0.03:
                    indices.append(index)

            elif hypothesis == "RANGE_BREAK":
                prior_high = max(highs[index - 10:index])
                prior_low = min(lows[index - 10:index])
                prior_range = prior_high / prior_low - 1.0 if prior_low > 0 else 0.0
                if prior_range <= 0.06 and closes[index] > prior_high:
                    indices.append(index)
            else:
                raise ValueError(f"Unsupported discovery hypothesis: {hypothesis}")

        return indices

    HYPOTHESES: tuple[tuple[str, str], ...] = (
        ("BREAKOUT_EXPANSION", "Выход из сжатия с расширением диапазона"),
        ("PULLBACK_RECLAIM", "Откат внутри восходящей структуры и возврат выше fast average"),
        ("IMPULSE_CONTINUATION", "Сильный импульс с последующим подтверждением продолжения"),
        ("SHOCK_REVERSAL", "Экстремальное отрицательное движение и последующая реакция"),
        ("GAP_REVERSAL", "Сильный отрицательный gap и последующая реакция"),
        ("RANGE_BREAK", "Выход из узкого диапазона"),
    )

    @classmethod
    def _evidence_for_indices(cls, candles: Sequence[Candle], indices: Sequence[int], horizon: int, baseline: Sequence[float]) -> DiscoveryHorizonEvidence:
        values = [value for index in indices if (value := cls._forward_return(candles, index, horizon)) is not None]
        baseline_mean = mean(baseline) * 100.0 if baseline else 0.0
        event_mean = mean(values) * 100.0 if values else 0.0
        return DiscoveryHorizonEvidence(
            horizon=horizon,
            observations=len(values),
            mean_forward_return_pct=event_mean,
            median_forward_return_pct=median(values) * 100.0 if values else 0.0,
            win_rate_pct=(sum(value > 0 for value in values) / len(values) * 100.0) if values else 0.0,
            baseline_mean_return_pct=baseline_mean,
            excess_return_pct=event_mean - baseline_mean,
        )

    @classmethod
    def run(cls, candles: Sequence[Candle]) -> ResearchDiscoveryResult:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        logger.warning("[V085 DISCOVERY START] candles=%d hypotheses=%d horizons=%s", len(ordered), len(cls.HYPOTHESES), cls.HORIZONS)
        if len(ordered) < cls.MIN_LOOKBACK + 1:
            logger.warning("[V085 DISCOVERY RESULT] status=INSUFFICIENT_DATA candles=%d minimum=%d", len(ordered), cls.MIN_LOOKBACK + 1)
            return ResearchDiscoveryResult(RESEARCH_DISCOVERY_VERSION, len(ordered), (), ())

        baselines = {
            horizon: cls._baseline(ordered, horizon)
            for horizon in cls.HORIZONS
        }
        baseline_evidence = tuple(
            DiscoveryHorizonEvidence(
                horizon=horizon,
                observations=len(values),
                mean_forward_return_pct=mean(values) * 100.0 if values else 0.0,
                median_forward_return_pct=median(values) * 100.0 if values else 0.0,
                win_rate_pct=(sum(value > 0 for value in values) / len(values) * 100.0) if values else 0.0,
                baseline_mean_return_pct=mean(values) * 100.0 if values else 0.0,
                excess_return_pct=0.0,
            )
            for horizon, values in baselines.items()
        )

        evidence: list[DiscoveryEvidence] = []
        for hypothesis, description in cls.HYPOTHESES:
            indices = cls._event_indices(ordered, hypothesis)
            horizons = tuple(cls._evidence_for_indices(ordered, indices, horizon, baselines[horizon]) for horizon in cls.HORIZONS)
            item = DiscoveryEvidence(
                hypothesis=hypothesis,
                description=description,
                events=len(indices),
                first_event=ordered[indices[0]].timestamp if indices else None,
                last_event=ordered[indices[-1]].timestamp if indices else None,
                horizons=horizons,
            )
            strongest = item.strongest_horizon
            logger.warning(
                "[V085 DISCOVERY HYPOTHESIS] hypothesis=%s events=%d strongest_horizon=%s excess=%.4f mean_return=%.4f win_rate=%.2f",
                hypothesis,
                item.events,
                strongest.horizon if strongest else None,
                strongest.excess_return_pct if strongest else 0.0,
                strongest.mean_forward_return_pct if strongest else 0.0,
                strongest.win_rate_pct if strongest else 0.0,
            )
            for horizon in horizons:
                logger.info(
                    "[V085 DISCOVERY HORIZON] hypothesis=%s horizon=%d observations=%d mean=%.4f median=%.4f win_rate=%.2f baseline=%.4f excess=%.4f",
                    hypothesis, horizon.horizon, horizon.observations, horizon.mean_forward_return_pct,
                    horizon.median_forward_return_pct, horizon.win_rate_pct,
                    horizon.baseline_mean_return_pct, horizon.excess_return_pct,
                )
            evidence.append(item)

        logger.warning("[V085 DISCOVERY RESULT] status=COMPLETE hypotheses=%d", len(evidence))
        return ResearchDiscoveryResult(RESEARCH_DISCOVERY_VERSION, len(ordered), baseline_evidence, tuple(evidence))


__all__ = [
    "RESEARCH_DISCOVERY_VERSION",
    "DiscoveryHorizonEvidence",
    "DiscoveryEvidence",
    "ResearchDiscoveryResult",
    "ResearchDiscoveryServiceV085",
]
