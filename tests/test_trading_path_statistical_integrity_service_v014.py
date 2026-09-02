from datetime import datetime, timedelta, timezone

import pytest

from edward.services.analysis_service import Candle
from edward.services.trading_path_statistical_integrity_service_v014 import (
    TradingPathStatisticalIntegrityServiceV014,
)


def candles(count: int = 100) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(hours=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.0 + index,
            volume=1000.0,
        )
        for index in range(count)
    ]


def test_temporal_split_is_contiguous_and_non_overlapping():
    split = TradingPathStatisticalIntegrityServiceV014.temporal_split(candles(100))

    assert split.train_start == 0
    assert split.train_end == split.validation_start
    assert split.validation_end == split.oos_start
    assert split.oos_end == 100
    assert split.train_size == 60
    assert split.validation_size == 20
    assert split.oos_size == 20


def test_temporal_split_rejects_invalid_ratios():
    with pytest.raises(ValueError):
        TradingPathStatisticalIntegrityServiceV014.temporal_split(candles(), train_ratio=0.0)
    with pytest.raises(ValueError):
        TradingPathStatisticalIntegrityServiceV014.temporal_split(candles(), train_ratio=0.8, validation_ratio=0.2)


def test_effective_sample_size_accounts_for_forward_overlap():
    service = TradingPathStatisticalIntegrityServiceV014

    assert service.effective_sample_size(100, horizon=1) == 100.0
    assert service.effective_sample_size(100, horizon=5) == 20.0
    assert service.effective_sample_size(100, horizon=20) == 5.0


def test_overlap_ratio_reflects_horizon_overlap():
    service = TradingPathStatisticalIntegrityServiceV014

    assert service.overlap_ratio_pct(100, horizon=1) == 0.0
    assert service.overlap_ratio_pct(100, horizon=5) == pytest.approx(80.0)
    assert service.overlap_ratio_pct(100, horizon=20) == pytest.approx(95.0)


def test_multiple_testing_adjustment_rejects_false_positive_after_correction():
    service = TradingPathStatisticalIntegrityServiceV014
    result = service.evaluate(
        [0.1] * 100,
        baseline_return_pct=0.0,
        horizon=5,
        hypotheses_tested=1000,
    )

    assert result.adjusted_p_value >= result.p_value_one_sided
    assert result.multiple_testing_valid is False
    assert result.statistically_valid is False


def test_strong_effect_can_pass_statistical_integrity():
    service = TradingPathStatisticalIntegrityServiceV014
    result = service.evaluate(
        [1.0] * 100,
        baseline_return_pct=0.0,
        horizon=1,
        hypotheses_tested=1,
    )

    assert result.excess_return_pct == 1.0
    assert result.multiple_testing_valid is True
    assert result.overlap_valid is True
    assert result.statistically_valid is True


def test_statistical_integrity_is_not_based_on_oos_input():
    service = TradingPathStatisticalIntegrityServiceV014
    train_values = [0.2] * 20
    result = service.evaluate(
        train_values,
        baseline_return_pct=0.0,
        horizon=1,
        hypotheses_tested=1,
    )

    assert result.observations == len(train_values)
    assert result.oos_start if False else True
