from __future__ import annotations

from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import AnalysisResult, Candle, StrategyResult
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.research_backtest_service_v08 import BacktestCostModel


def _candles(count: int = 900) -> list[Candle]:
    result: list[Candle] = []
    price = 100.0
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    for index in range(count):
        drift = 0.0012 if index < 500 else -0.0004 if index < 650 else 0.0009
        price *= 1.0 + drift
        result.append(Candle(start + timedelta(days=index), price, price, price, price, 1000 + index))
    return result


def test_v08_returns_existing_analysis_result_type_and_fields():
    result = AnalysisServiceV08().analyze(
        instrument_uid="uid-v08",
        ticker="TEST-V08",
        candles=_candles(),
        profile="medium_term",
    )

    assert isinstance(result, AnalysisResult)
    assert result.analysis_version == "0.8.0"
    assert isinstance(result.strategies, list)
    assert len(result.strategies) == 4
    assert all(isinstance(item, StrategyResult) for item in result.strategies)
    assert result.recommendation in {None, "Trend Following", "Momentum", "Breakout", "Mean Reversion"}
    assert result.market_regime in {"TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOLATILITY", "LOW_VOLATILITY", "TRANSITION", "UNKNOWN"}


def test_v08_keeps_strategy_output_names_stable():
    result = AnalysisServiceV08().analyze(
        instrument_uid="uid-v08-names",
        ticker="TEST-V08-NAMES",
        candles=_candles(),
        profile="medium_term",
    )
    assert {item.strategy for item in result.strategies} == {
        "Trend Following",
        "Momentum",
        "Breakout",
        "Mean Reversion",
    }


def test_v08_cost_model_is_injected_without_changing_output_contract():
    result = AnalysisServiceV08(
        costs=BacktestCostModel(commission_pct=0.1, spread_pct=0.1, slippage_pct=0.1)
    ).analyze(
        instrument_uid="uid-v08-cost",
        ticker="TEST-V08-COST",
        candles=_candles(),
        profile="medium_term",
    )
    assert isinstance(result, AnalysisResult)
    assert all(isinstance(item.score, float) for item in result.strategies)


def test_v08_exposes_research_diagnostics_without_contract_extension():
    service = AnalysisServiceV08()
    result = service.analyze(
        instrument_uid="uid-v08-diag",
        ticker="TEST-V08-DIAG",
        candles=_candles(),
        profile="medium_term",
    )
    assert result.instrument_uid == "uid-v08-diag"
    assert service.last_diagnostics is not None
    assert service.last_diagnostics.regime == result.market_regime
    assert set(service.last_diagnostics.robustness_by_strategy) == {
        "Trend Following",
        "Momentum",
        "Breakout",
        "Mean Reversion",
    }
