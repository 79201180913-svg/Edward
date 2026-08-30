from edward.services.train_activity_diagnostics_v084 import TrainActivityDiagnosticsServiceV084
from edward.services.research_backtest_service_v08 import ResearchBacktestResult


def _result(trades: int) -> ResearchBacktestResult:
    return ResearchBacktestResult(
        strategy="Breakout",
        parameters={},
        gross_return_pct=1.0,
        net_return_pct=1.0,
        benchmark_return_pct=0.0,
        excess_return_pct=1.0,
        max_drawdown_pct=1.0,
        sharpe=1.0,
        sortino=1.0,
        calmar=1.0,
        trades=trades,
        win_rate_pct=50.0,
        profit_factor=1.0,
        payoff_ratio=1.0,
        turnover_pct=1.0,
        exposure_pct=50.0,
        average_trade_pct=0.2,
        median_trade_pct=0.2,
        best_trade_pct=1.0,
        worst_trade_pct=-1.0,
        positive_days_pct=50.0,
        equity=(1.0,),
        trades_detail=(),
    )


def test_no_trades_is_classified_without_changing_selection() -> None:
    result = TrainActivityDiagnosticsServiceV084.classify(_result(0))
    assert result.classification == TrainActivityDiagnosticsServiceV084.NO_TRADES
    assert result.trades == 0


def test_one_to_four_trades_are_low_sample_by_default() -> None:
    for trades in (1, 2, 4):
        result = TrainActivityDiagnosticsServiceV084.classify(_result(trades))
        assert result.classification == TrainActivityDiagnosticsServiceV084.LOW_SAMPLE


def test_five_or_more_trades_are_adequate_by_default() -> None:
    result = TrainActivityDiagnosticsServiceV084.classify(_result(5))
    assert result.classification == TrainActivityDiagnosticsServiceV084.ADEQUATE_SAMPLE


def test_threshold_is_configurable() -> None:
    result = TrainActivityDiagnosticsServiceV084.classify(_result(3), adequate_min_trades=3)
    assert result.classification == TrainActivityDiagnosticsServiceV084.ADEQUATE_SAMPLE
