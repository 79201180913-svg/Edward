from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import AnalysisResult, Candle, StrategyResult
from edward.services.expected_value_engine_v08 import ExpectedValueEngine
from edward.services.opportunity_engine_v08 import OpportunityEngineV08
from edward.services.portfolio_impact_service_v08 import PortfolioImpactService


def _candles(count: int = 180) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    values = [100.0 + index * 0.5 for index in range(count)]
    return [Candle(start + timedelta(days=i), value, value, value, value) for i, value in enumerate(values)]


def _analysis(strategy: str = "Momentum") -> AnalysisResult:
    result = StrategyResult(
        strategy=strategy,
        parameters={"lookback": 2},
        return_pct=12.0,
        max_drawdown_pct=5.0,
        sharpe=1.2,
        trades=20,
        stability=80.0,
        quality_gate=True,
        score=78.0,
    )
    return AnalysisResult(
        instrument_uid="uid",
        ticker="TEST",
        profile="medium_term",
        risk_profile="balanced",
        horizon="medium",
        market_regime="Trend",
        recommendation=strategy,
        confidence="High",
        score=78.0,
        strategies=[result],
        explanation="test",
        created_at="2026-08-28T00:00:00+00:00",
    )


def _portfolio(candles: list[Candle]):
    returns = [candles[i].close / candles[i - 1].close - 1.0 for i in range(1, len(candles))]
    return PortfolioImpactService.calculate(
        weights={"existing": 1.0},
        asset_returns={"existing": returns, "candidate": returns},
        candidate_id="candidate",
        candidate_weight=0.1,
        candidate_expected_return_pct=10.0,
    )


def test_v08_returns_existing_opportunity_result_contract():
    analysis = _analysis()
    candles = _candles()
    strategy = analysis.strategies[0]
    ev = ExpectedValueEngine.from_returns([3.0, 4.0, 5.0, -1.0, -2.0] * 10)
    result = OpportunityEngineV08.evaluate(
        analysis=analysis,
        candles=candles,
        strategy_result=strategy,
        expected_value=ev,
        portfolio_impact=_portfolio(candles),
    )

    assert hasattr(result, "context")
    assert hasattr(result, "score")
    assert hasattr(result, "entry_signal")
    assert hasattr(result, "market_regime_compatible")
    assert hasattr(result, "explanation")
    assert hasattr(result, "risk")
    assert 0.0 <= result.score <= 100.0


def test_negative_expected_value_blocks_strategy_quality():
    analysis = _analysis()
    candles = _candles()
    strategy = analysis.strategies[0]
    ev = ExpectedValueEngine.from_returns([2.0, -3.0] * 40)
    result = OpportunityEngineV08.evaluate(
        analysis=analysis,
        candles=candles,
        strategy_result=strategy,
        expected_value=ev,
        portfolio_impact=_portfolio(candles),
    )

    assert result.context.strategy_ok is False


def test_positive_expected_value_is_reflected_in_score():
    analysis = _analysis()
    candles = _candles()
    strategy = analysis.strategies[0]
    ev = ExpectedValueEngine.from_returns([5.0, 4.0, 6.0, -1.0] * 30)
    result = OpportunityEngineV08.evaluate(
        analysis=analysis,
        candles=candles,
        strategy_result=strategy,
        expected_value=ev,
        portfolio_impact=_portfolio(candles),
    )

    assert result.context.strategy_ok is True
    assert result.score > 0.0
    assert "EV=" in result.explanation
