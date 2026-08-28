from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.research_backtest_v08 import BacktestCostModel, ResearchBacktestService


def _candles(prices: list[float]) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(days=i),
            open=price,
            high=price * 1.01,
            low=price * 0.99,
            close=price,
            volume=1000.0,
        )
        for i, price in enumerate(prices)
    ]


def test_backtest_uses_next_open_after_close_signal_and_tracks_gap():
    candles = _candles([100.0, 100.0, 120.0, 110.0])

    def signal(_candles, index):
        return index == 1

    result = ResearchBacktestService().run(candles, strategy="TEST", signal=signal)

    # Signal at day 2 close enters at day 3 open. Signal turns off at day 3
    # close and exits at day 4 open. There is no hidden same-bar execution.
    assert result.trades == 1
    assert result.trade_returns_pct[0] < 0
    assert result.net_return_pct < 0


def test_transaction_costs_reduce_net_result():
    candles = _candles([100.0, 100.0, 110.0, 110.0])

    def signal(_candles, index):
        return index == 1

    free = ResearchBacktestService(cost_model=BacktestCostModel()).run(
        candles, strategy="TEST", signal=signal
    )
    costly = ResearchBacktestService(
        cost_model=BacktestCostModel(commission_bps=10, spread_bps=10, slippage_bps=5)
    ).run(candles, strategy="TEST", signal=signal)

    assert costly.net_return_pct < free.net_return_pct
    assert costly.total_cost_pct > 0


def test_benchmark_and_extended_metrics_are_returned():
    candles = _candles([100.0, 105.0, 110.0, 115.0, 120.0])

    def signal(_candles, index):
        return index >= 1

    result = ResearchBacktestService().run(candles, strategy="TEST", signal=signal)

    assert result.benchmark_return_pct > 0
    assert result.excess_return_pct != 0
    assert result.trades == 1
    assert 0 <= result.win_rate_pct <= 100
    assert result.turnover >= 2
    assert 0 <= result.exposure_pct <= 100
    assert len(result.equity_curve) >= 2


def test_invalid_negative_cost_is_rejected():
    try:
        BacktestCostModel(commission_bps=-1)
    except ValueError as exc:
        assert "negative" in str(exc).lower()
    else:
        raise AssertionError("Negative costs must be rejected")
