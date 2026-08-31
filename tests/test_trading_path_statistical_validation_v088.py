import pytest

from edward.services.trading_path_statistical_validation_v088 import TradingPathStatisticalValidationV088


def test_statistical_evidence_reports_descriptive_metrics_and_ci():
    result = TradingPathStatisticalValidationV088.evaluate((1.0, 2.0, -1.0, 2.0))
    assert result.observations == 4
    assert result.mean_return_pct == pytest.approx(1.0)
    assert result.median_return_pct == pytest.approx(1.5)
    assert result.win_rate_pct == pytest.approx(75.0)
    assert result.std_return_pct > 0
    assert result.ci95_low_pct < result.mean_return_pct < result.ci95_high_pct
    assert result.positive_mean is True


def test_temporal_validation_counts_positive_blocks():
    result = TradingPathStatisticalValidationV088.evaluate(
        (1.0, 2.0, -1.0, 2.0),
        ((1.0, 2.0), (-1.0, -2.0), (0.5, 0.25)),
    )
    assert len(result.temporal_blocks) == 3
    assert result.positive_temporal_blocks == 2
    assert result.temporal_blocks[1].mean_return_pct == pytest.approx(-1.5)


def test_empty_evidence_is_safe():
    result = TradingPathStatisticalValidationV088.evaluate(())
    assert result.observations == 0
    assert result.mean_return_pct == 0.0
    assert result.win_rate_pct == 0.0
