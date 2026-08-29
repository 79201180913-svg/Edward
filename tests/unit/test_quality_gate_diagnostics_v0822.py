from __future__ import annotations

from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.quality_gate_diagnostics_v0822 import QualityGateDiagnosticsServiceV0822
from edward.services.robust_walk_forward_service_v08 import ParameterStability, RobustWalkForwardResult


def _result(
    *,
    windows: int = 6,
    mean_return: float = 1.0,
    mean_drawdown: float = 10.0,
    mean_sharpe: float = 0.5,
    return_consistency: float = 66.67,
    robustness: float = 70.0,
) -> RobustWalkForwardResult:
    return RobustWalkForwardResult(
        strategy="Breakout",
        windows=tuple(object() for _ in range(windows)),
        mean_test_return_pct=mean_return,
        median_test_return_pct=mean_return,
        std_test_return_pct=0.0,
        worst_test_return_pct=mean_return,
        best_test_return_pct=mean_return,
        mean_test_drawdown_pct=mean_drawdown,
        mean_test_sharpe=mean_sharpe,
        positive_return_windows=round(windows * return_consistency / 100.0),
        risk_ok_windows=windows,
        positive_sharpe_windows=windows,
        return_consistency_pct=return_consistency,
        risk_consistency_pct=100.0,
        sharpe_consistency_pct=100.0,
        robustness_score=robustness,
        parameter_stability=ParameterStability(windows, windows, 100.0, ()),
    )


def test_quality_gate_diagnostics_pass_when_all_existing_rules_pass():
    result = _result()
    diagnostics = QualityGateDiagnosticsServiceV0822.evaluate(result, "speculative")

    assert diagnostics.passed is True
    assert diagnostics.failed_checks == ()
    assert all(check.passed for check in diagnostics.checks)


def test_quality_gate_diagnostics_identifies_return_consistency_failure():
    result = _result(return_consistency=50.0, robustness=64.0)
    diagnostics = QualityGateDiagnosticsServiceV0822.evaluate(result, "speculative")

    assert diagnostics.passed is False
    assert "Положительные OOS окна" in diagnostics.failed_checks
    assert "Robustness Score" not in diagnostics.failed_checks
    assert diagnostics.failure_reason == "Положительные OOS окна"


def test_quality_gate_diagnostics_preserves_profile_thresholds():
    result = _result(mean_drawdown=28.0, robustness=59.0)

    speculative = QualityGateDiagnosticsServiceV0822.evaluate(result, "speculative")
    medium = QualityGateDiagnosticsServiceV0822.evaluate(result, "medium_term")

    assert speculative.passed is True
    assert medium.passed is False
    assert "Средняя OOS просадка" in medium.failed_checks
    assert "Robustness Score" in medium.failed_checks


def test_analysis_service_exposes_diagnostics_for_every_strategy_without_changing_gate():
    from datetime import datetime, timedelta, timezone

    candles = []
    price = 100.0
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    for index in range(900):
        drift = 0.0012 if index < 500 else -0.0004 if index < 650 else 0.0009
        price *= 1.0 + drift
        from edward.services.analysis_service import Candle
        candles.append(Candle(start + timedelta(days=index), price, price, price, price, 1000 + index))

    service = AnalysisServiceV08()
    result = service.analyze(
        instrument_uid="uid-v0822",
        ticker="TEST-V0822",
        candles=candles,
        profile="speculative",
    )

    assert service.last_diagnostics is not None
    assert set(service.last_diagnostics.quality_gate_by_strategy) == {item.strategy for item in result.strategies}
    for item in result.strategies:
        diagnostics = service.last_diagnostics.quality_gate_by_strategy[item.strategy]
        assert diagnostics.passed is item.quality_gate
        assert diagnostics.profile == "speculative"


def test_quality_gate_logs_each_check(caplog):
    result = _result(return_consistency=50.0, robustness=64.0)

    with caplog.at_level("INFO", logger="edward.services.analysis_service_v08"):
        AnalysisServiceV08._quality(result, "speculative")

    text = caplog.text
    assert "[QUALITY GATE] strategy=Breakout profile=speculative result=FAIL" in text
    assert "check=wf_windows" in text
    assert "check=mean_test_return" in text
    assert "check=mean_test_drawdown" in text
    assert "check=mean_test_sharpe" in text
    assert "check=return_consistency" in text
    assert "check=robustness_score" in text
    assert "failed_checks=('Положительные OOS окна',)" in text
