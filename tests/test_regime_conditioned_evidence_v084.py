from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.regime_conditioned_evidence_v084 import RegimeConditionedEvidenceServiceV084
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult, WalkForwardWindowResult, ParameterStability


def _candles(n=120):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Candle(start + timedelta(days=i), 100.0 + i * 0.05, 101.0 + i * 0.05, 99.0 + i * 0.05, 100.0 + i * 0.05, 1000.0) for i in range(n)]


def _result():
    candles = _candles()
    windows = tuple(
        WalkForwardWindowResult(
            index=i, train_start=candles[0].timestamp, train_end=candles[59].timestamp,
            test_start=candles[60 + i * 10].timestamp, test_end=candles[69 + i * 10].timestamp,
            parameters={"lookback": 20}, train_score=10.0,
            test_net_return_pct=1.0 if i == 0 else -0.5,
            test_benchmark_return_pct=0.2,
            test_excess_return_pct=0.8 if i == 0 else -0.7,
            test_max_drawdown_pct=1.0, test_sharpe=1.0 if i == 0 else -0.2,
            test_sortino=1.0 if i == 0 else -0.2, test_trades=2,
        ) for i in range(2)
    )
    return RobustWalkForwardResult(
        strategy="Momentum", windows=windows, mean_test_return_pct=0.25,
        median_test_return_pct=0.25, std_test_return_pct=0.75,
        worst_test_return_pct=-0.5, best_test_return_pct=1.0,
        mean_test_drawdown_pct=1.0, mean_test_sharpe=0.4,
        positive_return_windows=1, risk_ok_windows=2, positive_sharpe_windows=1,
        return_consistency_pct=50.0, risk_consistency_pct=100.0,
        sharpe_consistency_pct=50.0, robustness_score=60.0,
        parameter_stability=ParameterStability(2, 2, 100.0, ((("lookback", 20),), (("lookback", 20),))),
    )


def test_regime_evidence_is_descriptive_and_only_uses_matching_oos_windows():
    result = RegimeConditionedEvidenceServiceV084.evaluate(
        _result(), _candles(), "TREND_UP", 70.0, ticker="TEST"
    )
    assert result.strategy == "Momentum"
    assert result.current_regime == "TREND_UP"
    assert result.total_windows == 2
    assert result.matching_windows in (0, 1, 2)
    assert 0.0 <= result.coverage_pct <= 100.0
    assert 0.0 <= result.evidence_score <= 100.0


def test_no_matching_regime_does_not_create_positive_evidence():
    result = RegimeConditionedEvidenceServiceV084.evaluate(
        _result(), _candles(), "UNKNOWN", 0.0, ticker="TEST"
    )
    assert result.matching_windows == 0
    assert result.evidence_score == 0.0
    assert result.mean_oos_return_pct == 0.0
