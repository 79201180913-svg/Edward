from types import SimpleNamespace

from edward.domain import TradingPathAnalysisV012, TradingPathOpportunity, TradingPathDecision
from edward.services.trading_path_pipeline_diagnostics_v012 import TradingPathPipelineDiagnosticsServiceV012


def _analysis():
    return TradingPathAnalysisV012(
        instrument_uid="uid-1",
        ticker="RZSB",
        strategy_family="Breakout",
        hypothesis="BREAKOUT_EXPANSION",
        regime="TREND_UP",
        volatility_bucket="High",
        direction="Positive",
        horizon=10,
        evidence=SimpleNamespace(),
        validation=SimpleNamespace(promotion_status="research_only"),
        opportunity=TradingPathOpportunity(
            score=71.5,
            confidence=64.0,
            expected_value_pct=2.5,
            risk_score=82.0,
            risk_gate=True,
        ),
        decision=TradingPathDecision.WAIT,
        rank=1,
    )


def test_collect_preserves_path_level_diagnostics():
    rows = TradingPathPipelineDiagnosticsServiceV012.collect((_analysis(),))
    assert len(rows) == 1
    row = rows[0]
    assert row.ticker == "RZSB"
    assert row.rank == 1
    assert row.validation_status == "research_only"
    assert row.opportunity_score == 71.5
    assert row.opportunity_confidence == 64.0
    assert row.expected_value_pct == 2.5
    assert row.risk_score == 82.0
    assert row.risk_gate is True
    assert row.decision == "wait"


def test_collect_handles_missing_opportunity_and_validation():
    analysis = _analysis()
    analysis = TradingPathAnalysisV012(
        instrument_uid=analysis.instrument_uid,
        ticker=analysis.ticker,
        strategy_family=analysis.strategy_family,
        hypothesis=analysis.hypothesis,
        regime=analysis.regime,
        volatility_bucket=analysis.volatility_bucket,
        direction=analysis.direction,
        horizon=analysis.horizon,
        evidence=analysis.evidence,
        validation=None,
        opportunity=None,
        decision=TradingPathDecision.WAIT,
        rank=None,
    )
    row = TradingPathPipelineDiagnosticsServiceV012.collect((analysis,))[0]
    assert row.validation_status is None
    assert row.opportunity_score is None
    assert row.expected_value_pct is None
    assert row.risk_score is None
    assert row.risk_gate is None
    assert row.decision == "wait"
