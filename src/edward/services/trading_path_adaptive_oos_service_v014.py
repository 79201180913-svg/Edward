from __future__ import annotations

import logging
from statistics import mean
from typing import Sequence

from edward.domain import TradingPathCandidate
from edward.services.analysis_service import Candle
from edward.services.regime_engine_v08 import RegimeEngine
from edward.services.trading_path_adaptive_discovery_service_v014 import AdaptiveRuleConditionV014
from edward.services.trading_path_feature_service_v014 import TradingPathFeatureServiceV014

logger = logging.getLogger(__name__)
ADAPTIVE_OOS_VERSION = "0.8.14"


class TradingPathAdaptiveOOSServiceV014:
    """Point-in-time execution of an adaptive rule on validation/OOS candles.

    The rule and thresholds are immutable inputs produced by TRAIN discovery. This
    service never derives thresholds, baselines or conditions from the evaluation
    partition. It only evaluates whether each candle satisfies the supplied rule and
    calculates realized forward returns for the rule horizon.
    """

    VERSION = ADAPTIVE_OOS_VERSION

    @staticmethod
    def is_adaptive(candidate: TradingPathCandidate) -> bool:
        return candidate.rule.hypothesis.upper().startswith("ADAPTIVE_RULE:")

    @staticmethod
    def _forward_return(candles: Sequence[Candle], index: int, horizon: int) -> float | None:
        finish = index + horizon
        if index < 0 or finish >= len(candles):
            return None
        start = float(candles[index].close)
        end = float(candles[finish].close)
        if start <= 0.0 or end <= 0.0:
            return None
        return (end / start - 1.0) * 100.0

    @classmethod
    def matching_indices(
        cls,
        candidate: TradingPathCandidate,
        candles: Sequence[Candle],
    ) -> tuple[int, ...]:
        """Return point-in-time indices satisfying the candidate's adaptive rule."""
        if not cls.is_adaptive(candidate):
            return ()
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        conditions = tuple(
            cls._parse_conditions(candidate.rule.hypothesis)
        )
        if not conditions:
            return ()
        features = TradingPathFeatureServiceV014.build(ordered)
        feature_map = {(item.name, item.index): item.value for item in features}
        result: list[int] = []
        horizon = candidate.rule.horizon
        for index in range(len(ordered)):
            if index + horizon >= len(ordered):
                continue
            if RegimeEngine.classify(ordered[: index + 1]).regime != candidate.rule.regime:
                continue
            if all(
                condition.matches(feature_map.get((condition.feature, index)))
                for condition in conditions
            ):
                result.append(index)
        return tuple(result)

    @staticmethod
    def _parse_conditions(hypothesis: str) -> tuple[AdaptiveRuleConditionV014, ...]:
        prefix = "ADAPTIVE_RULE:"
        if not hypothesis.upper().startswith(prefix):
            return ()
        expression = hypothesis[len(prefix):]
        parts = expression.split(" AND ")
        if not parts or not parts[0].startswith("regime="):
            return ()
        conditions: list[AdaptiveRuleConditionV014] = []
        for part in parts[1:]:
            tokens = part.rsplit(" ", 2)
            if len(tokens) != 3:
                return ()
            feature, operator, threshold_text = tokens
            if operator not in {">=", "<="}:
                return ()
            try:
                threshold = float(threshold_text)
            except ValueError:
                return ()
            conditions.append(AdaptiveRuleConditionV014(feature, operator, threshold))
        return tuple(conditions)

    @classmethod
    def returns_in_range(
        cls,
        candidate: TradingPathCandidate,
        candles: Sequence[Candle],
        *,
        start: int,
        end: int,
    ) -> tuple[float, ...]:
        """Evaluate a supplied adaptive rule inside one isolated evaluation range."""
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        if start < 0 or end < start:
            raise ValueError("invalid evaluation range")
        matches = cls.matching_indices(candidate, ordered)
        values = tuple(
            value
            for index in matches
            if start <= index < end
            if (value := cls._forward_return(ordered, index, candidate.rule.horizon)) is not None
        )
        logger.warning(
            "[V014 ADAPTIVE OOS] ticker=%s regime=%s horizon=%d range=%d:%d matches=%d "
            "mean_return_pct=%s train_thresholds_immutable=True",
            candidate.rule.ticker, candidate.rule.regime, candidate.rule.horizon,
            start, end, len(values), mean(values) if values else None,
        )
        return values


__all__ = ["ADAPTIVE_OOS_VERSION", "TradingPathAdaptiveOOSServiceV014"]
