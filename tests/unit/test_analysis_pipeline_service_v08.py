from datetime import datetime, timedelta, timezone

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineServiceV08
from edward.services.analysis_service import Candle


def _candles(count: int = 360) -> list[Candle]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    result: list[Candle] = []
    for index in range(count):
        step = 0.002 if index % 9 else -0.001
        price *= 1.0 + step
        result.append(Candle(start + timedelta(days=index), price, price, price, price))
    return result


def test_pipeline_preserves_legacy_analysis_and_opportunity_shapes():
    result = AnalysisPipelineServiceV08().analyze(
        instrument_uid="candidate",
        ticker="TEST",
        candles=_candles(),
    )

    assert result.version == "0.8.0"
    assert result.analysis.analysis_version == "0.8.0"
    assert hasattr(result.opportunity, "context")
    assert hasattr(result.opportunity, "score")
    assert hasattr(result.opportunity, "risk")
    assert result.expected_value.version == "0.8.0"
    assert result.portfolio_impact.version == "0.8.0"


def test_pipeline_can_include_candidate_in_portfolio_impact():
    candles = _candles()
    returns = [candles[i].close / candles[i - 1].close - 1.0 for i in range(1, len(candles))]
    result = AnalysisPipelineServiceV08().analyze(
        instrument_uid="candidate",
        ticker="TEST",
        candles=candles,
        portfolio_weights={"existing": 0.9},
        portfolio_returns={"existing": returns},
        candidate_weight=0.1,
    )

    assert result.portfolio_impact.portfolio_risk_before_pct >= 0.0
    assert result.portfolio_impact.portfolio_risk_after_pct >= 0.0
    assert result.portfolio_impact.expected_return_impact_pct == result.portfolio_impact.expected_return_after_pct - result.portfolio_impact.expected_return_before_pct
