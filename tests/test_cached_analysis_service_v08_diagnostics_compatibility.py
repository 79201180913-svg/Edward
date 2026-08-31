from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.analysis_service import Candle, StrategyResult
from edward.services.cached_analysis_service_v08 import CachedAnalysisServiceV08


class FakeCache:
    def __init__(self, *_args, **_kwargs):
        self.saved = []

    def fingerprint(self, **_kwargs):
        return "fingerprint"

    def get(self, **_kwargs):
        strategy = _kwargs["strategy"]
        return (
            1,
            StrategyResult(
                strategy=strategy,
                parameters={},
                return_pct=2.5,
                max_drawdown_pct=5.0,
                sharpe=0.8,
                trades=12,
                stability=72.0,
                quality_gate=True,
                score=72.0,
                wf_windows=8,
                positive_return_windows=6,
                risk_ok_windows=8,
                positive_sharpe_windows=6,
                return_consistency=75.0,
                risk_consistency=100.0,
                sharpe_consistency=75.0,
            ),
        )


def test_cached_analysis_populates_quality_gate_diagnostics(monkeypatch):
    monkeypatch.setattr(
        "edward.services.cached_analysis_service_v08.StrategyOptimizationCache",
        FakeCache,
    )
    monkeypatch.setattr(
        "edward.services.cached_analysis_service_v08.RegimeEngine.classify",
        lambda _candles: SimpleNamespace(regime="TREND", confidence=80.0),
    )

    candles = [
        Candle(
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=index),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        )
        for index in range(300)
    ]

    result = CachedAnalysisServiceV08(store=None).analyze(
        instrument_uid="uid",
        ticker="TEST",
        candles=candles,
        profile="medium_term",
    )

    diagnostics = result.strategies
    assert len(diagnostics) == 4


def test_cached_analysis_diagnostics_expose_same_quality_gate_contract():
    strategy = StrategyResult(
        strategy="Breakout",
        parameters={"lookback": 20},
        return_pct=4.0,
        max_drawdown_pct=6.0,
        sharpe=1.2,
        trades=8,
        stability=82.0,
        quality_gate=True,
        score=82.0,
        wf_windows=10,
        return_consistency=70.0,
    )

    diagnostics = CachedAnalysisServiceV08._diagnostics_from_strategy_result(strategy, "medium_term")

    assert diagnostics.passed is True
    assert diagnostics.robustness_threshold == 60.0
    assert {check.key for check in diagnostics.checks} == {
        "wf_windows",
        "mean_test_return",
        "mean_test_drawdown",
        "mean_test_sharpe",
        "return_consistency",
        "robustness_score",
    }
