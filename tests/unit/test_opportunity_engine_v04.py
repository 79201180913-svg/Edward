from __future__ import annotations

from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import AnalysisResult, Candle, StrategyResult
from edward.services.opportunity_engine import OpportunityEngine


def _candles(count: int = 260) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    result = []
    price = 100.0
    for i in range(count):
        previous = price
        price *= 1.002
        result.append(Candle(start + timedelta(days=i), previous, price, previous, price, 1000.0))
    return result


def _analysis(regime: str = "Trend") -> AnalysisResult:
    return AnalysisResult(
        instrument_uid="uid",
        ticker="TEST",
        profile="medium_term",
        risk_profile="balanced",
        horizon="medium",
        market_regime=regime,
        recommendation="Momentum",
        confidence="High",
        score=80.0,
        strategies=[],
        explanation="",
        created_at="2026-08-25T00:00:00+00:00",
    )


def test_no_strategy_returns_zero_opportunity():
    result = OpportunityEngine.evaluate(_analysis(), _candles(), None)
    assert result.score == 0.0
    assert result.context.strategy_ok is False
    assert result.context.risk_ok is False


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
    assert result.risk is not None
    assert 0 <= result.score <= 100


def test_opportunity_score_uses_portfolio_fit():
    strategy = StrategyResult("Momentum", {"lookback": 20}, 15.0, 8.0, 1.2, 20, 80.0, True, 80.0)
    good = OpportunityEngine.evaluate(
        _analysis("Momentum"), _candles(), strategy,
        position_weight_pct=5.0, target_weight_pct=10.0, max_position_weight_pct=15.0,
        portfolio_available=True, available_cash=100000.0, estimated_trade_value=5000.0,
    )
    bad = OpportunityEngine.evaluate(
        _analysis("Momentum"), _candles(), strategy,
        position_weight_pct=30.0, target_weight_pct=10.0, max_position_weight_pct=15.0,
        portfolio_available=True,
    )
    assert good.risk is not None and bad.risk is not None
    assert good.risk.portfolio_fit_score > bad.risk.portfolio_fit_score
    assert good.score > bad.score
    assert bad.context.risk_ok is False
