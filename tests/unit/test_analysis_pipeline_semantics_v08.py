from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineServiceV08
from edward.services.analysis_service import Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.expected_value_engine_v08 import ExpectedValueEngine
from edward.services.regime_engine_v08 import RegimeEngine
from edward.services.research_backtest_service_v08 import BacktestTrade


def _candles(values: list[float]) -> list[Candle]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [Candle(start + timedelta(days=i), value, value, value, value) for i, value in enumerate(values)]


def test_expected_value_is_explicitly_unavailable_without_outcomes():
    result = ExpectedValueEngine.from_returns(())

    assert result.available is False
    assert result.unavailable_reason == "NO_REALIZED_OUTCOMES"


def test_expected_value_remains_available_when_quality_gate_would_be_weak():
    trades = tuple(
        BacktestTrade(None, None, 0.0, 0.0, value, 0.0, value)
        for value in (1.0, -0.5, 0.7, -0.2)
    )

    result = ExpectedValueEngine.from_trades(trades)

    assert result.available is True
    assert result.observations == 4
    assert result.expected_value_pct > 0


def test_regime_confidence_is_not_100_percent():
    candles = _candles([100 + index * 0.5 for index in range(120)])

    result = RegimeEngine.classify(candles)

    assert result.regime == "TREND_UP"
    assert 0.0 < result.confidence < 100.0


def test_pipeline_keeps_evidence_when_no_strategy_passes_quality_gate(monkeypatch: pytest.MonkeyPatch):
    candles = _candles([100 + index * 0.2 for index in range(420)])
    service = AnalysisPipelineServiceV08()

    monkeypatch.setattr(AnalysisServiceV08, "_quality", staticmethod(lambda _result, _profile: False))

    result = service.analyze(
        instrument_uid="UID",
        ticker="TEST",
        candles=candles,
        profile="medium_term",
    )

    assert result.analysis.recommendation is None
    assert result.evidence_strategy is not None
    assert result.expected_value.observations > 0
    assert result.expected_value.available is True
    assert result.forecast_quality_score is not None
    assert result.regime_confidence is not None
    assert 0.0 < result.regime_confidence < 100.0
    assert result.portfolio_context_available is False
