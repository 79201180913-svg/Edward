from datetime import datetime, timedelta, timezone

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.analysis_service import Candle
from edward.services.trading_path_expected_value_service_v012 import TradingPathExpectedValueServiceV012


def _candidate() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid-1",
            ticker="SBER",
            hypothesis="BREAKOUT_EXPANSION",
            regime="TREND_UP",
            volatility_bucket="Normal",
            direction="Positive",
            horizon=2,
        ),
        evidence=TradingPathEvidence(
            observations=20,
            mean_forward_return_pct=1.0,
            median_forward_return_pct=1.0,
            win_rate_pct=60.0,
            baseline_mean_return_pct=0.2,
            excess_return_pct=0.8,
            sufficient_sample=True,
        ),
    )


def _adaptive_candidate() -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid-1",
            ticker="SBER",
            hypothesis="ADAPTIVE_RULE:regime=TREND_UP AND return_5 >= 0.0",
            regime="TREND_UP",
            volatility_bucket="Adaptive",
            direction="Positive",
            horizon=2,
        ),
        evidence=TradingPathEvidence(
            observations=20,
            mean_forward_return_pct=1.0,
            median_forward_return_pct=1.0,
            win_rate_pct=60.0,
            baseline_mean_return_pct=0.2,
            excess_return_pct=0.8,
            sufficient_sample=True,
        ),
        source_version="0.8.14",
    )


def _candles(n: int = 130) -> list[Candle]:
    return [
        Candle(
            datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
            100.0 + i * 0.01,
            101.0 + i * 0.01,
            99.0 + i * 0.01,
            100.0 + i * 0.02,
            1000.0,
        )
        for i in range(n)
    ]


def test_path_ev_is_built_from_oos_path_outcomes_only():
    candidate = _candidate()
    candles = _candles()

    outcomes = TradingPathExpectedValueServiceV012.outcomes(candidate, candles)
    result = TradingPathExpectedValueServiceV012.calculate(candidate, candles)

    assert result.observations == len(outcomes)
    assert result.available is True if outcomes else result.available is False
    assert result.expected_value_pct == 0.0 if not outcomes else result.expected_value_pct >= 0.0


def test_insufficient_temporal_data_returns_unavailable_ev():
    result = TradingPathExpectedValueServiceV012.calculate(_candidate(), _candles(50))

    assert result.available is False
    assert result.observations == 0
    assert result.unavailable_reason == "NO_REALIZED_OUTCOMES"


def test_adaptive_candidate_uses_same_ev_outcome_contract(monkeypatch):
    calls = []

    def fake_returns_in_range(candidate, candles, *, start, end):
        calls.append((candidate.rule.hypothesis, start, end))
        return (1.0, -0.5)

    monkeypatch.setattr(
        "edward.services.trading_path_adaptive_oos_service_v014.TradingPathAdaptiveOOSServiceV014.returns_in_range",
        staticmethod(fake_returns_in_range),
    )

    candidate = _adaptive_candidate()
    candles = _candles()
    outcomes = TradingPathExpectedValueServiceV012.outcomes(
        candidate, candles, windows=2, test_size=10
    )
    result = TradingPathExpectedValueServiceV012.calculate(
        candidate, candles, windows=2, test_size=10
    )

    assert outcomes == (1.0, -0.5, 1.0, -0.5)
    assert result.observations == 4
    assert result.available is True
    assert len(calls) == 4


def test_fixed_candidate_does_not_use_adaptive_ev_evaluator(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("adaptive evaluator must not be used for fixed candidates")

    monkeypatch.setattr(
        "edward.services.trading_path_adaptive_oos_service_v014.TradingPathAdaptiveOOSServiceV014.returns_in_range",
        staticmethod(fail_if_called),
    )

    result = TradingPathExpectedValueServiceV012.calculate(
        _candidate(), _candles(), windows=2, test_size=10
    )

    assert result.observations >= 0
