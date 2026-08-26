from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import AnalysisService, Candle, StrategyResult


def candles(count: int = 150) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            timestamp=start + timedelta(days=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.0 + i,
        )
        for i in range(count)
    ]


def failed_strategy(strategy: str, profile: str) -> StrategyResult:
    return StrategyResult(
        strategy=strategy,
        parameters={},
        return_pct=-1.0,
        max_drawdown_pct=20.0,
        sharpe=-0.5,
        trades=3,
        stability=80.0,
        quality_gate=False,
        score=90.0,
    )


def test_analysis_confidence_is_na_when_all_strategies_fail_quality_gate(monkeypatch):
    monkeypatch.setattr(AnalysisService, "walk_forward", classmethod(lambda cls, candles, strategy, profile: failed_strategy(strategy, profile)))

    result = AnalysisService().analyze(
        instrument_uid="uid-1",
        ticker="TEST",
        candles=candles(),
        profile="medium_term",
    )

    assert result.recommendation is None
    assert result.confidence == "N/A"


def test_analysis_confidence_remains_high_for_passing_strategy(monkeypatch):
    def passing_strategy(cls, candles, strategy, profile):
        return StrategyResult(
            strategy=strategy,
            parameters={},
            return_pct=20.0,
            max_drawdown_pct=10.0,
            sharpe=2.0,
            trades=10,
            stability=90.0,
            quality_gate=True,
            score=90.0,
        )

    monkeypatch.setattr(AnalysisService, "walk_forward", classmethod(passing_strategy))

    result = AnalysisService().analyze(
        instrument_uid="uid-1",
        ticker="TEST",
        candles=candles(),
        profile="medium_term",
    )

    assert result.recommendation is not None
    assert result.confidence == "High"
