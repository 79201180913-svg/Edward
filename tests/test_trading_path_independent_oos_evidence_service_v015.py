from types import SimpleNamespace

from edward.services.trading_path_independent_oos_evidence_service_v015 import (
    TradingPathIndependentOOSEvidenceServiceV015,
)


def _window(start, end, observations, mean_return, baseline, excess):
    return SimpleNamespace(
        start=start,
        end=end,
        observations=observations,
        mean_return_pct=mean_return,
        baseline_return_pct=baseline,
        excess_return_pct=excess,
    )


def test_independent_oos_aggregates_locked_evidence():
    windows = (
        _window(120, 150, 5, 4.0, 1.0, 3.0),
        _window(150, 180, 4, 2.0, 1.0, 1.0),
        _window(180, 210, 3, -1.0, 0.0, -1.0),
    )

    result = TradingPathIndependentOOSEvidenceServiceV015.build(
        candidate_key=("uid", "TICKER", "hypothesis", "TREND_UP", "LOW", "LONG", 5),
        oos_windows=windows,
        validation_start=60,
        validation_end=120,
    )

    assert result.windows == 3
    assert result.observations == 12
    assert result.mean_return_pct == 1.6666666667
    assert result.mean_baseline_return_pct == 0.6666666667
    assert result.excess_return_pct == 1.0
    assert result.positive_windows_pct == 66.6666666667
    assert result.worst_window_excess_pct == -1.0
    assert result.median_window_excess_pct == 1.0
    assert result.status == "READY"
    assert result.parameters_locked is True


def test_independent_oos_rejects_validation_overlap():
    windows = (_window(110, 140, 3, 2.0, 1.0, 1.0),)

    result = TradingPathIndependentOOSEvidenceServiceV015.build(
        candidate_key=("candidate",),
        oos_windows=windows,
        validation_start=60,
        validation_end=120,
    )

    assert result.status == "INVALID_OVERLAP"
    assert result.parameters_locked is True
    assert result.excess_return_pct is None


def test_independent_oos_requires_minimum_observations():
    windows = (_window(120, 150, 2, 2.0, 1.0, 1.0),)

    result = TradingPathIndependentOOSEvidenceServiceV015.build(
        candidate_key=("candidate",),
        oos_windows=windows,
        validation_start=60,
        validation_end=120,
    )

    assert result.status == "INSUFFICIENT"
    assert result.observations == 2
    assert result.excess_return_pct == 1.0
    assert result.parameters_locked is True


def test_independent_oos_empty_set_is_not_a_pass():
    result = TradingPathIndependentOOSEvidenceServiceV015.build(
        candidate_key=("candidate",),
        oos_windows=(),
    )

    assert result.status == "INSUFFICIENT"
    assert result.windows == 0
    assert result.observations == 0
    assert result.excess_return_pct is None
    assert result.parameters_locked is True


def test_independent_oos_missing_window_metrics_is_insufficient():
    windows = (
        SimpleNamespace(
            start=120,
            end=150,
            observations=5,
            mean_return_pct=None,
            baseline_return_pct=1.0,
            excess_return_pct=None,
        ),
    )

    result = TradingPathIndependentOOSEvidenceServiceV015.build(
        candidate_key=("candidate",),
        oos_windows=windows,
    )

    assert result.status == "INSUFFICIENT"
    assert result.excess_return_pct is None
    assert result.parameters_locked is True
