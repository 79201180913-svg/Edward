from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.analysis_service import Candle
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSValidationServiceV012


def _cand() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid",
            ticker="SBER",
            hypothesis="BREAKOUT_EXPANSION",
            regime="RANGE",
            volatility_bucket="Normal",
            direction="Positive",
            horizon=2,
        ),
        evidence=TradingPathEvidence(
            observations=10,
            mean_forward_return_pct=1.0,
            median_forward_return_pct=1.0,
            win_rate_pct=60.0,
            baseline_mean_return_pct=0.0,
            excess_return_pct=1.0,
            sufficient_sample=True,
        ),
    )


def _adaptive_cand() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid",
            ticker="SBER",
            hypothesis="ADAPTIVE_RULE:regime=RANGE AND return_5 >= 0.0",
            regime="RANGE",
            volatility_bucket="Adaptive",
            direction="Positive",
            horizon=2,
        ),
        evidence=TradingPathEvidence(
            observations=20,
            mean_forward_return_pct=1.0,
            median_forward_return_pct=1.0,
            win_rate_pct=60.0,
            baseline_mean_return_pct=0.0,
            excess_return_pct=1.0,
            sufficient_sample=True,
        ),
        source_version="0.8.14",
    )


def _candles(n=80):
    return [
        Candle(
            datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
            100.0 + i * 0.2,
            101.0 + i * 0.2,
            99.0 + i * 0.2,
            100.0 + i * 0.2,
            1000.0,
        )
        for i in range(n)
    ]


def test_oos_validation_uses_fixed_path_and_returns_temporal_windows():
    result = TradingPathOOSValidationServiceV012.validate(_cand(), _candles(), windows=3, test_size=10)

    assert len(result) == 3
    assert [item.index for item in result] == [1, 2, 3]
    assert result[0].start < result[0].end
    assert result[0].end == result[1].start


def test_oos_validation_never_uses_discovery_evidence_as_oos_result():
    result = TradingPathOOSValidationServiceV012.validate(_cand(), _candles(), windows=2, test_size=10)

    assert all(item.observations >= 0 for item in result)
    assert all(item.excess_return_pct != 1.0 or item.observations == 0 for item in result)


def test_build_validation_produces_path_level_validation_summary():
    result = TradingPathOOSValidationServiceV012.build_validation(_cand(), _candles(), windows=2, test_size=10)

    assert result.candidate.rule.hypothesis == "BREAKOUT_EXPANSION"
    assert result.validation.wf_persistence_pct is not None
    assert result.validation.positive_oos_windows_pct is not None
    assert result.validation.statistical_valid in (True, False)
    assert result.validation.promotion_status in ("validated", "rejected")


def test_oos_validation_returns_empty_when_not_enough_data():
    result = TradingPathOOSValidationServiceV012.validate(_cand(), _candles(20), windows=4, test_size=10)

    assert result == ()


def test_adaptive_candidate_uses_same_oos_window_contract(monkeypatch):
    calls = []

    def fake_returns_in_range(candidate, candles, *, start, end):
        calls.append((candidate.rule.hypothesis, start, end))
        return (1.0, 2.0)

    monkeypatch.setattr(
        "edward.services.trading_path_adaptive_oos_service_v014.TradingPathAdaptiveOOSServiceV014.returns_in_range",
        staticmethod(fake_returns_in_range),
    )

    result = TradingPathOOSValidationServiceV012.validate(
        _adaptive_cand(), _candles(), windows=2, test_size=10
    )

    assert len(result) == 2
    assert [item.observations for item in result] == [2, 2]
    assert [item.index for item in result] == [1, 2]
    assert [item.start for item in result] == [60, 70]
    assert [item.end for item in result] == [70, 80]
    assert len(calls) == 2


def test_fixed_candidate_does_not_use_adaptive_evaluator(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("adaptive evaluator must not be used for fixed candidates")

    monkeypatch.setattr(
        "edward.services.trading_path_adaptive_oos_service_v014.TradingPathAdaptiveOOSServiceV014.returns_in_range",
        staticmethod(fail_if_called),
    )

    result = TradingPathOOSValidationServiceV012.validate(
        _cand(), _candles(), windows=2, test_size=10
    )

    assert len(result) == 2


def test_explicit_evaluation_range_does_not_cross_range_end():
    matching_event = SimpleNamespace(
        index=79,
        hypothesis="BREAKOUT_EXPANSION",
        regime="RANGE",
        volatility_bucket="Normal",
        direction="Positive",
    )

    monkeypatch_observations = lambda candles: (matching_event,)
    original = TradingPathOOSValidationServiceV012._evaluate_window
    try:
        from edward.services.event_observation_v086 import EventObservationBuilderV086
        EventObservationBuilderV086.build = staticmethod(monkeypatch_observations)
        result = TradingPathOOSValidationServiceV012.validate(
            _cand(),
            _candles(100),
            windows=1,
            test_size=20,
            evaluation_start=60,
            evaluation_end=80,
        )
    finally:
        EventObservationBuilderV086.build = staticmethod(original)

    assert len(result) == 1
    assert result[0].start == 60
    assert result[0].end == 80
    assert result[0].observations == 0
