from __future__ import annotations

from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import AnalysisResult, Candle, StrategyResult
from edward.services.opportunity_engine import OpportunityEngine


def _candles(count: int = 20) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = []
    price = 100.0
    for i in range(count):
        price *= 1.001
        result.append(Candle(start + timedelta(days=i), price, price, price, price, 1000))
    return result


def _analysis(regime: str = "Trend") -> AnalysisResult:
    return AnalysisResult(
        instrument_uid="uid",
        ticker="TEST",
        profile="medium_term",
        risk_profile="balanced",
        horizon="medium",
        market_regime=regime,
        recommendation=None,
        confidence="Low",
        score=0.0,
        strategies=[],
        explanation="",
        created_at="2026-08-25T00:00:00+00:00",
    )


def test_no_strategy_returns_zero_opportunity():
    result = OpportunityEngine.evaluate(_analysis(), _candles(), None)
    assert result.score == 0.0
    assert result.context.strategy_ok is False
    assert result.context.risk_ok is True


def test_quality_strategy_produces_opportunity_context():
    strategy = StrategyResult(
        strategy="Trend Following",
        parameters={"fast": 10, "slow": 30},
        return_pct=12.0,
        max_drawdown_pct=8.0,
        sharpe=1.0,
        trades=20,
        stability=80.0,
        quality_gate=True,
        score=75.0,
    )
    result = OpportunityEngine.evaluate(_analysis("Trend"), _candles(), strategy)
    assert result.context.strategy_ok is True
    assert result.context.risk_ok is True
    assert 0 <= result.score <= 100
