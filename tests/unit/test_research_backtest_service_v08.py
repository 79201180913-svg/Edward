from __future__ import annotations

from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestService


def _candles(values: list[float]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [Candle(start + timedelta(days=i), value, value, value, value) for i, value in enumerate(values)]


def test_signal_is_executed_on_next_candle_open():
    candles = _candles([100, 100, 110, 120])

    result = ResearchBacktestService.run(
        candles=candles,
        strategy="TEST",
        parameters={},
        signal_fn=lambda _items, index: index == 0,
    )

    assert result.trades == 1
    trade = result.trades_detail[0]
    assert trade.entry_timestamp == candles[1].timestamp
    assert trade.entry_price == 100
    assert trade.exit_price == 110
    assert trade.gross_return_pct == 10.0


def test_costs_reduce_net_trade_return():
    candles = _candles([100, 100, 110])

    gross = ResearchBacktestService.run(
        candles=candles,
        strategy="TEST",
        parameters={},
        signal_fn=lambda _items, index: index == 0,
        costs=BacktestCostModel(),
    )
    costly = ResearchBacktestService.run(
        candles=candles,
        strategy="TEST",
        parameters={},
        signal_fn=lambda _items, index: index == 0,
        costs=BacktestCostModel(commission_pct=0.5, spread_pct=0.2, slippage_pct=0.1),
    )

    assert costly.trades == gross.trades == 1
    assert costly.trades_detail[0].net_return_pct < gross.trades_detail[0].net_return_pct
    assert costly.net_return_pct < gross.net_return_pct


def test_backtest_uses_same_equity_path_for_drawdown_and_net_return():
    candles = _candles([100, 100, 110, 90, 120])

    result = ResearchBacktestService.run(
        candles=candles,
        strategy="TEST",
        parameters={},
        signal_fn=lambda _items, index: index in {0, 1},
    )

    assert len(result.equity) == len(candles) + 1
    assert result.net_return_pct == (result.equity[-1] - 1.0) * 100.0
    assert result.max_drawdown_pct >= 0.0


def test_benchmark_and_excess_return_are_reported():
    candles = _candles([100, 110, 120])

    result = ResearchBacktestService.run(
        candles=candles,
        strategy="TEST",
        parameters={},
        signal_fn=lambda _items, index: index == 0,
    )

    assert result.benchmark_return_pct == 20.0
    assert result.excess_return_pct < 0.0


def test_extended_metrics_are_returned():
    candles = _candles([100, 100, 105, 95, 110, 100])

    result = ResearchBacktestService.run(
        candles=candles,
        strategy="TEST",
        parameters={},
        signal_fn=lambda _items, index: index in {0, 2, 4},
    )

    assert result.version == "0.8.0"
    assert result.sortino != float("nan")
    assert result.trades >= 1
    assert result.turnover_pct > 0
    assert 0 <= result.exposure_pct <= 100


def test_simple_strategy_runner_supports_existing_strategy_names():
    candles = _candles([100, 101, 103, 104, 106, 108, 110])

    result = ResearchBacktestService.run_simple_strategy(
        candles=candles,
        strategy="Momentum",
        parameters={"lookback": 2},
    )

    assert result.strategy == "Momentum"
    assert result.parameters == {"lookback": 2}
