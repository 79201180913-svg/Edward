from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import AnalysisResult, Candle, StrategyResult
from edward.services.analysis_service_v08 import AnalysisServiceV08
from edward.services.expected_value_engine_v08 import ExpectedValueEngine
from edward.services.opportunity_engine import OpportunityResult
from edward.services.opportunity_engine_v08 import OpportunityEngineV08
from edward.services.portfolio_impact_service_v08 import PortfolioImpactService


def _candles(count: int = 420) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    values = []
    for index in range(count):
        price *= 1.0 + (0.0015 if index % 8 else -0.0008)
        values.append(price)
    return [Candle(start + timedelta(days=i), value, value, value, value) for i, value in enumerate(values)]


def test_analysis_result_legacy_fields_are_unchanged():
    result = AnalysisServiceV08().analyze(
        instrument_uid="uid",
        ticker="TEST",
        candles=_candles(),
        profile="medium_term",
    )

    required = {
        "instrument_uid", "ticker", "profile", "risk_profile", "horizon",
        "market_regime", "recommendation", "confidence", "score", "strategies",
        "explanation", "created_at", "analysis_version",
    }
    assert required.issubset(result.__dataclass_fields__)
    assert result.analysis_version == "0.8.7"
    assert all({
        "strategy", "parameters", "return_pct", "max_drawdown_pct", "sharpe",
        "trades", "stability", "quality_gate", "score", "train_score", "test_score",
        "wf_windows", "positive_return_windows", "risk_ok_windows",
        "positive_sharpe_windows", "return_consistency", "risk_consistency", "sharpe_consistency",
    }.issubset(item.__dataclass_fields__) for item in result.strategies)


def test_opportunity_result_legacy_fields_are_unchanged():
    candles = _candles()
    strategy = StrategyResult(
        "Momentum", {"lookback": 2}, 5.0, 4.0, 1.0, 20, 75.0, True, 75.0,
    )
    analysis = AnalysisResult(
        "uid", "TEST", "medium_term", "balanced", "medium", "TREND_UP",
        "Momentum", "High", 75.0, [strategy], "test", candles[-1].timestamp.isoformat(), "0.8.7",
    )
    ev = ExpectedValueEngine.from_returns([4.0, 5.0, 6.0, -1.0] * 20)
    impact = PortfolioImpactService.calculate(
        weights={"existing": 1.0},
        asset_returns={"existing": [0.001] * 100, "uid": [0.002] * 100},
        candidate_id="uid",
        candidate_weight=0.1,
        candidate_expected_return_pct=ev.expected_value_pct,
    )
    result = OpportunityEngineV08.evaluate(
        analysis=analysis,
        candles=candles,
        strategy_result=strategy,
        expected_value=ev,
        portfolio_impact=impact,
    )

    assert isinstance(result, OpportunityResult)
    assert {"context", "score", "entry_signal", "market_regime_compatible", "explanation", "risk"}.issubset(result.__dataclass_fields__)
