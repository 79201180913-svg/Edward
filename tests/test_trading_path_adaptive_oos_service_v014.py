from datetime import datetime, timedelta, timezone

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.analysis_service import Candle
from edward.services.regime_engine_v08 import RegimeEngine
from edward.services.trading_path_adaptive_oos_service_v014 import TradingPathAdaptiveOOSServiceV014


def candles(count: int = 140) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result: list[Candle] = []
    for index in range(count):
        close = 100.0 + index * 0.7
        result.append(Candle(
            timestamp=start + timedelta(hours=index),
            open=close - 0.2,
            high=close + 0.8,
            low=close - 0.8,
            close=close,
            volume=1000.0 + index,
        ))
    return result


def adaptive_candidate(candles_: list[Candle]) -> TradingPathCandidate:
    regime = RegimeEngine.classify(candles_[:61]).regime
    return TradingPathCandidate(
        rule=TradingPathRule(
            "uid", "TEST", "ADAPTIVE_RULE:regime=" + regime + " AND return_5 >= -100", regime,
            "Adaptive", "Positive", 5,
        ),
        evidence=TradingPathEvidence(60, 3.5, 3.5, 100.0, 3.0, 0.5, True),
        source_version="0.8.14",
    )


def test_adaptive_rule_matches_by_point_in_time_conditions():
    sample = candles()
    candidate = adaptive_candidate(sample)
    matches = TradingPathAdaptiveOOSServiceV014.matching_indices(candidate, sample)

    assert matches
    assert all(index >= 0 for index in matches)
    assert matches == tuple(sorted(matches))


def test_adaptive_rule_returns_are_limited_to_requested_range():
    sample = candles()
    candidate = adaptive_candidate(sample)
    values = TradingPathAdaptiveOOSServiceV014.returns_in_range(candidate, sample, start=72, end=96)

    assert values
    assert len(values) <= 24
    assert all(value > 0.0 for value in values)


def test_fixed_candidate_is_not_evaluated_by_adaptive_service():
    candidate = TradingPathCandidate(
        rule=TradingPathRule("uid", "TEST", "BREAKOUT_EXPANSION", "TREND_UP", "Normal", "Positive", 5),
        evidence=TradingPathEvidence(8, 1.0, 1.0, 60.0, 0.2, 0.8, True),
    )

    assert TradingPathAdaptiveOOSServiceV014.is_adaptive(candidate) is False
    assert TradingPathAdaptiveOOSServiceV014.matching_indices(candidate, candles()) == ()


def test_adaptive_rule_does_not_derive_new_thresholds_from_evaluation_data():
    sample = candles()
    candidate = adaptive_candidate(sample)
    baseline_matches = TradingPathAdaptiveOOSServiceV014.matching_indices(candidate, sample)

    changed = list(sample)
    for index in range(96, len(changed)):
        candle = changed[index]
        changed[index] = Candle(
            timestamp=candle.timestamp,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close * 3.0,
            volume=candle.volume,
        )

    changed_matches = TradingPathAdaptiveOOSServiceV014.matching_indices(candidate, changed)

    baseline_evaluation_matches = tuple(index for index in baseline_matches if 72 <= index < 96)
    changed_evaluation_matches = tuple(index for index in changed_matches if 72 <= index < 96)

    assert changed_evaluation_matches == baseline_evaluation_matches


def test_adaptive_rule_returns_reflect_realized_evaluation_data():
    sample = candles()
    candidate = adaptive_candidate(sample)
    baseline_matches = tuple(
        index
        for index in TradingPathAdaptiveOOSServiceV014.matching_indices(candidate, sample)
        if 72 <= index < 96 and index + candidate.rule.horizon >= 96
    )
    assert baseline_matches

    target_index = baseline_matches[-1]
    target_finish = target_index + candidate.rule.horizon
    baseline = TradingPathAdaptiveOOSServiceV014.returns_in_range(candidate, sample, start=72, end=96)

    changed = list(sample)
    candle = changed[target_finish]
    changed[target_finish] = Candle(
        timestamp=candle.timestamp,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close * 3.0,
        volume=candle.volume,
    )
    repeated = TradingPathAdaptiveOOSServiceV014.returns_in_range(candidate, changed, start=72, end=96)

    assert repeated != baseline
    assert len(repeated) == len(baseline)
