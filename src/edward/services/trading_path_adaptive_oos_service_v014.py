from __future__ import annotations

import logging
from collections import OrderedDict
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
    """Point-in-time execution of a TRAIN-derived adaptive rule.

    The rule and thresholds are immutable inputs produced by TRAIN discovery.
    Evaluation ranges only determine which already-known rule matches are scored;
    forward returns are never allowed to cross the end of the evaluation range.

    The point-in-time feature/regime context is cached by candle fingerprint so
    evaluating many adaptive candidates does not rebuild the same context for
    every candidate or evaluation window.
    """

    VERSION = ADAPTIVE_OOS_VERSION
    _CONTEXT_CACHE_MAXSIZE = 8
    _CONTEXT_CACHE: OrderedDict[tuple[tuple[object, float, float, float, float, float], ...], tuple[tuple[Candle, ...], dict[tuple[str, int], float], tuple[str, ...]]] = OrderedDict()

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
    def _context_key(cls, candles: Sequence[Candle]) -> tuple[tuple[object, float, float, float, float, float], ...]:
        return tuple(
            (
                item.timestamp,
                float(item.open),
                float(item.high),
                float(item.low),
                float(item.close),
                float(item.volume),
            )
            for item in candles
        )

    @classmethod
    def _prepared_context(
        cls,
        candles: Sequence[Candle],
    ) -> tuple[tuple[Candle, ...], dict[tuple[str, int], float], tuple[str, ...]]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        key = cls._context_key(ordered)
        cached = cls._CONTEXT_CACHE.get(key)
        if cached is not None:
            cls._CONTEXT_CACHE.move_to_end(key)
            return cached

        features = TradingPathFeatureServiceV014.build(ordered)
        feature_map = {(item.name, item.index): item.value for item in features}
        regimes = tuple(
            RegimeEngine.classify(ordered[: index + 1]).regime
            for index in range(len(ordered))
        )
        context = (ordered, feature_map, regimes)
        cls._CONTEXT_CACHE[key] = context
        cls._CONTEXT_CACHE.move_to_end(key)
        while len(cls._CONTEXT_CACHE) > cls._CONTEXT_CACHE_MAXSIZE:
            cls._CONTEXT_CACHE.popitem(last=False)
        logger.warning(
            "[V014 ADAPTIVE OOS CONTEXT] candles=%d features=%d cached=True",
            len(ordered), len(features),
        )
        return context

    @classmethod
    def matching_indices(
        cls,
        candidate: TradingPathCandidate,
        candles: Sequence[Candle],
    ) -> tuple[int, ...]:
        """Return point-in-time indices satisfying the candidate's adaptive rule."""
        if not cls.is_adaptive(candidate):
            return ()
        ordered, feature_map, regimes = cls._prepared_context(candles)
        conditions = tuple(cls._parse_conditions(candidate.rule.hypothesis))
        if not conditions:
            return ()
        result: list[int] = []
        horizon = candidate.rule.horizon
        for index in range(len(ordered)):
            if index + horizon >= len(ordered):
                continue
            if regimes[index] != candidate.rule.regime:
                continue
            if all(condition.matches(feature_map.get((condition.feature, index))) for condition in conditions):
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
        """Evaluate a supplied adaptive rule inside an isolated range."""
        ordered, _, _ = cls._prepared_context(candles)
        if start < 0 or end < start or end > len(ordered):
            raise ValueError("invalid evaluation range")
        matches = cls.matching_indices(candidate, ordered)
        values = tuple(
            value
            for index in matches
            if start <= index < end
            if index + candidate.rule.horizon < end
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
