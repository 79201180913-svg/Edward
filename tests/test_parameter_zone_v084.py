from edward.services.parameter_zone_v084 import ParameterZoneServiceV084
from edward.services.research_backtest_service_v08 import ResearchBacktestResult


def _result(excess: float, sharpe: float = 1.0, dd: float = 2.0) -> ResearchBacktestResult:
    return ResearchBacktestResult(
        strategy="Breakout",
        parameters={"lookback": 20},
        gross_return_pct=excess + 1.0,
        net_return_pct=excess + 1.0,
        benchmark_return_pct=1.0,
        excess_return_pct=excess,
        max_drawdown_pct=dd,
        sharpe=sharpe,
        sortino=sharpe,
        calmar=0.5,
        trades=5,
        win_rate_pct=60.0,
        profit_factor=1.5,
        payoff_ratio=1.2,
        turnover_pct=10.0,
        exposure_pct=50.0,
        average_trade_pct=0.4,
        median_trade_pct=0.3,
        best_trade_pct=1.5,
        worst_trade_pct=-1.0,
        positive_days_pct=55.0,
        equity=(1.0, 1.01),
        trades_detail=(),
    )


def test_parameter_zone_uses_only_viable_train_candidates() -> None:
    candidates = [
        ({"lookback": 10}, _result(1.0)),
        ({"lookback": 20}, _result(2.0)),
        ({"lookback": 40}, _result(1.5)),
    ]
    viable = candidates
    zone = ParameterZoneServiceV084.evaluate(strategy="Breakout", candidates=candidates, viable=viable)
    assert zone.representative_parameters == {"lookback": 20}
    assert zone.viable_candidates == 3
    assert zone.viability_pct == 100.0
    assert zone.stable is True


def test_parameter_zone_is_not_stable_without_multiple_viable_candidates() -> None:
    candidates = [
        ({"lookback": 20}, _result(2.0)),
        ({"lookback": 40}, _result(-1.0)),
    ]
    viable = [candidates[0]]
    zone = ParameterZoneServiceV084.evaluate(strategy="Breakout", candidates=candidates, viable=viable)
    assert zone.representative_parameters == {"lookback": 20}
    assert zone.stable is False
    assert zone.viability_pct == 50.0


def test_parameter_zone_has_no_representative_without_viable_candidates() -> None:
    zone = ParameterZoneServiceV084.evaluate(strategy="Momentum", candidates=[], viable=[])
    assert zone.representative_parameters == {}
    assert zone.stable is False
