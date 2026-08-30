from edward.services.economic_viability_service_v084 import EconomicViabilityServiceV084
from edward.services.research_backtest_service_v08 import ResearchBacktestResult


def make_result(*, excess: float, net: float = 1.0, dd: float = 5.0, trades: int = 5) -> ResearchBacktestResult:
    return ResearchBacktestResult(
        strategy="Momentum",
        parameters={"lookback": 20},
        gross_return_pct=net,
        net_return_pct=net,
        benchmark_return_pct=net - excess,
        excess_return_pct=excess,
        max_drawdown_pct=dd,
        sharpe=1.0,
        sortino=1.0,
        calmar=1.0,
        trades=trades,
        win_rate_pct=60.0,
        profit_factor=1.5,
        payoff_ratio=1.2,
        turnover_pct=10.0,
        exposure_pct=20.0,
        average_trade_pct=0.2,
        median_trade_pct=0.2,
        best_trade_pct=1.0,
        worst_trade_pct=-0.5,
        positive_days_pct=55.0,
        equity=(1.0, 1.01),
        trades_detail=(),
    )


def test_negative_excess_is_not_eligible_even_with_good_risk_metrics():
    result = EconomicViabilityServiceV084.evaluate(make_result(excess=-1.0, dd=2.0, trades=20))

    assert result.eligible is False
    assert result.reasons == (EconomicViabilityServiceV084.NEGATIVE_EXCESS_RETURN,)


def test_viable_train_candidate_is_eligible():
    result = EconomicViabilityServiceV084.evaluate(make_result(excess=0.5, dd=10.0, trades=5))

    assert result.eligible is True
    assert result.reasons == ()


def test_drawdown_and_activity_are_independent_blockers():
    result = EconomicViabilityServiceV084.evaluate(
        make_result(excess=0.5, dd=20.0, trades=1),
        max_drawdown_pct=15.0,
        min_trades=3,
    )

    assert result.eligible is False
    assert EconomicViabilityServiceV084.EXCESSIVE_DRAWDOWN in result.reasons
    assert EconomicViabilityServiceV084.INSUFFICIENT_TRADES in result.reasons


def test_viability_does_not_use_oos_fields():
    result = make_result(excess=0.25, net=1.0, dd=5.0, trades=4)
    decision = EconomicViabilityServiceV084.evaluate(result)

    assert decision.eligible is True
    assert decision.min_excess_return_pct == 0.0
