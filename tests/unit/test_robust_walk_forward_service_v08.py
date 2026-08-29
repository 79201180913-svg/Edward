from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestService
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardService


def _candles(count: int = 420) -> list[Candle]:
    values: list[float] = []
    price = 100.0
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(count):
        price *= 1.001 if (i // 20) % 2 == 0 else 0.999
        values.append(price)
    return [Candle(start + timedelta(days=i), v, v, v, v) for i, v in enumerate(values)]


def test_rolling_walk_forward_produces_out_of_sample_windows():
    result = RobustWalkForwardService.run(
        candles=_candles(),
        strategy="Momentum",
        parameter_grid=[{"lookback": 5}, {"lookback": 10}],
        signal_factory=lambda strategy, params: lambda items, index: ResearchBacktestService.simple_signal(strategy, items, params, index),
        train_size=120,
        test_size=40,
        costs=BacktestCostModel(commission_pct=0.1),
        max_drawdown_pct=30.0,
    )

    assert len(result.windows) >= 5
    assert 0 <= result.return_consistency_pct <= 100
    assert 0 <= result.parameter_stability.stability_pct <= 100
    assert result.version == "0.8.0"
    assert result.worst_test_return_pct <= result.best_test_return_pct


def test_parameter_stability_detects_dominant_selection():
    result = RobustWalkForwardService.run(
        candles=_candles(),
        strategy="Momentum",
        parameter_grid=[{"lookback": 5}],
        signal_factory=lambda strategy, params: lambda items, index: ResearchBacktestService.simple_signal(strategy, items, params, index),
        train_size=120,
        test_size=40,
    )

    assert result.parameter_stability.windows == len(result.windows)
    assert result.parameter_stability.dominant_windows == len(result.windows)
    assert result.parameter_stability.stability_pct == 100.0


def test_v083_walk_forward_diagnostics_report_data_sufficiency(caplog):
    service = AnalysisServiceV08()

    with caplog.at_level(logging.INFO):
        result = service._robust(_candles(540), "Momentum", "medium_term")

    messages = [record.getMessage() for record in caplog.records]
    assert len(result.windows) == 5
    assert any("status=DATA_SUFFICIENT" in message for message in messages)
    assert any("[WALK FORWARD WINDOW] strategy=Momentum index=0" in message for message in messages)
    assert any("[WALK FORWARD SUMMARY] strategy=Momentum completed_windows=5" in message for message in messages)


def test_v083_walk_forward_diagnostics_distinguish_insufficient_windows(caplog):
    service = AnalysisServiceV08()

    with caplog.at_level(logging.INFO):
        result = service._robust(_candles(539), "Momentum", "medium_term")

    messages = [record.getMessage() for record in caplog.records]
    assert len(result.windows) == 4
    assert any("status=INSUFFICIENT_DATA" in message for message in messages)
    assert any("available_windows=4" in message and "required_windows=5" in message for message in messages)
    assert any("required_candles=540" in message for message in messages)
