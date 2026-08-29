from __future__ import annotations

from datetime import datetime, timezone

from edward.services.quality_gate_diagnostics_v0822 import QualityGateDiagnosticsServiceV0822
from edward.services.robust_walk_forward_service_v08 import (
    ParameterStability,
    RobustWalkForwardResult,
    WalkForwardWindowResult,
)


def _result() -> RobustWalkForwardResult:
    windows = tuple(
        WalkForwardWindowResult(
            index=index,
            train_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
            train_end=datetime(2025, 1, 10, tzinfo=timezone.utc),
            test_start=datetime(2025, 1, 11, tzinfo=timezone.utc),
            test_end=datetime(2025, 1, 20, tzinfo=timezone.utc),
            parameters={"lookback": 20},
            train_score=12.5,
            test_net_return_pct=-1.5 if index == 0 else 2.0,
            test_benchmark_return_pct=1.0,
            test_excess_return_pct=-2.5 if index == 0 else 1.0,
            test_max_drawdown_pct=5.0,
            test_sharpe=-0.2 if index == 0 else 0.4,
            test_sortino=-0.3 if index == 0 else 0.6,
            test_trades=3,
        )
        for index in range(5)
    )
    return RobustWalkForwardResult(
        strategy="Momentum",
        windows=windows,
        mean_test_return_pct=1.3,
        median_test_return_pct=2.0,
        std_test_return_pct=1.4,
        worst_test_return_pct=-1.5,
        best_test_return_pct=2.0,
        mean_test_drawdown_pct=5.0,
        mean_test_sharpe=0.28,
        positive_return_windows=4,
        risk_ok_windows=5,
        positive_sharpe_windows=4,
        return_consistency_pct=80.0,
        risk_consistency_pct=100.0,
        sharpe_consistency_pct=80.0,
        robustness_score=75.0,
        parameter_stability=ParameterStability(
            windows=5,
            dominant_windows=5,
            stability_pct=100.0,
            selected_parameters=tuple((("lookback", 20),) for _ in range(5)),
        ),
    )


def test_v083_quality_gate_logging_exposes_summary_windows_and_checks(caplog):
    caplog.set_level("INFO")

    diagnostics = QualityGateDiagnosticsServiceV0822.evaluate(_result(), "medium_term")

    assert diagnostics.passed is True
    messages = [record.getMessage() for record in caplog.records]
    assert any("[V083 QG WF SUMMARY]" in message for message in messages)
    assert sum("[V083 WF WINDOW]" in message for message in messages) == 5
    assert any("[V083 QG PARAMETER STABILITY]" in message for message in messages)
    assert sum("[V083 QG CHECK]" in message for message in messages) == 6
    assert any("[V083 QG RESULT]" in message and "passed=True" in message for message in messages)
