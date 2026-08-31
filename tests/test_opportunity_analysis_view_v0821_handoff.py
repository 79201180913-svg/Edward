from types import SimpleNamespace

from edward.services.opportunity_analysis_pipeline_v0821 import OpportunityAnalysisPipelineV0821


def _strategy(name: str, score: float):
    return SimpleNamespace(strategy=name, score=score)


def test_view_from_result_adapts_precomputed_result_without_running_analysis():
    selected = _strategy("breakout", 82.0)
    result = SimpleNamespace(
        analysis=SimpleNamespace(
            strategies=(selected, _strategy("trend_following", 71.0)),
            market_regime="BULL",
        ),
        evidence_strategy="breakout",
        opportunity=SimpleNamespace(score=74.0),
        confidence=SimpleNamespace(overall_confidence=88.0),
        trading_path_research=SimpleNamespace(version="0.8.8"),
    )

    view = OpportunityAnalysisPipelineV0821.view_from_result(result)

    assert view.pipeline_result is result
    assert view.strategies == (selected,)
    assert view.market_regime == "BULL"
    assert view.confidence == 88.0
    assert view.opportunity is result.opportunity
    assert view.pipeline_result.trading_path_research.version == "0.8.8"


def test_view_from_result_falls_back_to_best_strategy_when_evidence_strategy_missing():
    best = _strategy("mean_reversion", 91.0)
    result = SimpleNamespace(
        analysis=SimpleNamespace(strategies=(best, _strategy("breakout", 64.0))),
        evidence_strategy="missing",
        opportunity=SimpleNamespace(score=60.0),
        confidence=None,
    )

    view = OpportunityAnalysisPipelineV0821.view_from_result(result)

    assert view.strategies == (best,)
    assert view.confidence is None
