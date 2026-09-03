from datetime import datetime, timedelta, timezone

from edward.domain import TradingPathCandidate, TradingPathEvidence, TradingPathRule
from edward.services.analysis_service import Candle
from edward.services.trading_path_walk_forward_service_v015 import (
    TradingPathWalkForwardServiceV015,
)


def _candidate() -> TradingPathCandidate:
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
            observations=20,
            mean_forward_return_pct=1.0,
            median_forward_return_pct=1.0,
            win_rate_pct=60.0,
            baseline_mean_return_pct=0.0,
            excess_return_pct=1.0,
            sufficient_sample=True,
        ),
    )


def _candles(n=180):
    return [
        Candle(
            datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
            100.0 + i * 0.1,
            101.0 + i * 0.1,
            99.0 + i * 0.1,
            100.0 + i * 0.1,
            1000.0,
        )
        for i in range(n)
    ]


def test_build_windows_are_sequential_and_unseen():
    windows = TradingPathWalkForwardServiceV015.build_windows(
        _candles(), windows=4, train_size=60, validation_size=30
    )

    assert len(windows) == 4
    assert windows[0] == (0, 60, 60, 90)
    assert windows[1] == (0, 90, 90, 120)
    assert windows[2] == (0, 120, 120, 150)
    assert windows[3] == (0, 150, 150, 180)


def test_build_windows_returns_empty_when_history_is_insufficient():
    assert TradingPathWalkForwardServiceV015.build_windows(
        _candles(179), windows=4, train_size=60, validation_size=30
    ) == ()


def test_walk_forward_evaluates_each_validation_window_independently(monkeypatch):
    calls = []

    class FakeValidation:
        @staticmethod
        def validate(candidate, candles, **kwargs):
            calls.append(kwargs)
            start = kwargs["evaluation_start"]
            return (
                type(
                    "Window",
                    (),
                    {
                        "observations": 5,
                        "mean_return_pct": 2.0,
                        "baseline_return_pct": 1.0,
                        "excess_return_pct": 1.0,
                        "win_rate_pct": 60.0,
                        "positive": True,
                    },
                )(),
            )

    result = TradingPathWalkForwardServiceV015.validate_candidate(
        _candidate(), _candles(), windows=4, train_size=60, validation_size=30,
        evaluator=FakeValidation,
    )

    assert [(call["evaluation_start"], call["evaluation_end"]) for call in calls] == [
        (60, 90), (90, 120), (120, 150), (150, 180)
    ]
    assert result.wf_windows == 4
    assert result.positive_windows == 4
    assert result.persistence_pct == 100.0
    assert result.worst_window_excess_pct == 1.0
    assert result.passed is True


def test_walk_forward_fails_when_worst_window_is_non_positive():
    class FakeValidation:
        counter = 0

        @staticmethod
        def validate(candidate, candles, **kwargs):
            FakeValidation.counter += 1
            excess = 1.0 if FakeValidation.counter < 4 else -0.1
            return (
                type(
                    "Window",
                    (),
                    {
                        "observations": 5,
                        "mean_return_pct": excess + 1.0,
                        "baseline_return_pct": 1.0,
                        "excess_return_pct": excess,
                        "win_rate_pct": 60.0,
                        "positive": excess > 0,
                    },
                )(),
            )

    result = TradingPathWalkForwardServiceV015.validate_candidate(
        _candidate(), _candles(), windows=4, train_size=60, validation_size=30,
        evaluator=FakeValidation,
    )

    assert result.persistence_pct == 75.0
    assert result.worst_window_excess_pct == -0.1
    assert result.passed is False


def test_walk_forward_requires_minimum_observations_in_every_window():
    class FakeValidation:
        counter = 0

        @staticmethod
        def validate(candidate, candles, **kwargs):
            FakeValidation.counter += 1
            observations = 2 if FakeValidation.counter == 2 else 5
            return (
                type(
                    "Window",
                    (),
                    {
                        "observations": observations,
                        "mean_return_pct": 2.0,
                        "baseline_return_pct": 1.0,
                        "excess_return_pct": 1.0,
                        "win_rate_pct": 60.0,
                        "positive": True,
                    },
                )(),
            )

    result = TradingPathWalkForwardServiceV015.validate_candidate(
        _candidate(), _candles(), windows=4, train_size=60, validation_size=30,
        evaluator=FakeValidation,
    )

    assert result.sample_sufficiency is False
    assert result.passed is False


def test_walk_forward_returns_empty_summary_for_insufficient_history():
    result = TradingPathWalkForwardServiceV015.validate_candidate(
        _candidate(), _candles(100), windows=4, train_size=60, validation_size=30
    )

    assert result.wf_windows == 0
    assert result.persistence_pct is None
    assert result.passed is False
