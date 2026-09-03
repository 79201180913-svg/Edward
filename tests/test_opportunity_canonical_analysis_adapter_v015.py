from edward.domain import (
    TradingPathAnalysisStatus,
    TradingPathAnalysisV012,
    TradingPathCurrentState,
    TradingPathDecision,
    TradingPathOpportunity,
    TradingPathValidationSummary,
)
from edward.services.opportunity_canonical_analysis_adapter_v015 import CanonicalOpportunityAnalysisV015


def _analysis(
    *,
    rank: int,
    hypothesis: str = "BREAKOUT_EXPANSION",
    score: float = 10.0,
    decision: TradingPathDecision = TradingPathDecision.BUY,
    quality_gate_passed: bool | None = None,
) -> TradingPathAnalysisV012:
    evidence = type("Evidence", (), {"mean_forward_return_pct": 2.5, "max_drawdown_pct": 4.0, "observations": 12})()
    quality_gate = None
    if quality_gate_passed is not None:
        quality_gate = type("QualityGate", (), {"passed": quality_gate_passed})()
    independent_oos = type(
        "IndependentOOS",
        (),
        {"windows": (1, 2), "positive_windows_pct": 100.0, "excess_return_pct": 1.5},
    )()
    return TradingPathAnalysisV012(
        instrument_uid="uid",
        ticker="SBER",
        strategy_family="Adaptive Discovery",
        hypothesis=hypothesis,
        regime="TREND_DOWN",
        volatility_bucket="Adaptive",
        direction="Positive",
        horizon=20,
        evidence=evidence,
        validation=TradingPathValidationSummary(
            wf_persistence_pct=100.0,
            robustness_score=80.0,
            positive_oos_windows_pct=100.0,
            statistical_valid=True,
            overlap_valid=True,
            multiple_testing_valid=True,
            promotion_status="validated",
        ),
        opportunity=TradingPathOpportunity(score=score, confidence=0.75, expected_value_pct=2.0, risk_score=20.0, risk_gate=True),
        current_state=TradingPathCurrentState.ENTRY_READY,
        decision=decision,
        status=TradingPathAnalysisStatus.VALIDATED,
        rank=rank,
        independent_oos_evidence=independent_oos,
        quality_gate=quality_gate,
    )


def test_adapter_exposes_canonical_best_result_and_legacy_strategy_shape():
    analysis = _analysis(rank=1, hypothesis="ADAPTIVE_RULE:regime=TREND_DOWN AND distance_to_low_20 <= 0.04", quality_gate_passed=True)
    view = CanonicalOpportunityAnalysisV015.from_analyses([analysis])

    assert view.market_regime == "TREND_DOWN"
    assert view.confidence == 0.75
    assert view.opportunity == analysis.opportunity
    assert view.best_analysis is analysis
    assert len(view.strategies) == 1
    strategy = view.strategies[0]
    assert strategy.strategy == "Adaptive Discovery"
    assert strategy.parameters["hypothesis"].startswith("ADAPTIVE_RULE:")
    assert strategy.parameters["source"] == "adaptive"
    assert strategy.quality_gate is True
    assert strategy.trades == 12
    assert strategy.wf_windows == 2
    assert strategy.positive_return_windows == 2
    assert strategy.test_score == 1.5
    assert strategy.return_consistency == 100.0


def test_adapter_best_analysis_prefers_business_decision_before_rank():
    passing_rank_1 = _analysis(rank=1, score=1.0, decision=TradingPathDecision.PASS)
    wait_rank_2 = _analysis(rank=2, hypothesis="RANGE_BREAK", score=100.0, decision=TradingPathDecision.WAIT)
    buy_rank_3 = _analysis(rank=3, hypothesis="BREAKOUT", score=0.1, decision=TradingPathDecision.BUY)
    view = CanonicalOpportunityAnalysisV015.from_analyses([passing_rank_1, wait_rank_2, buy_rank_3])

    assert view.best_analysis is buy_rank_3
    assert view.canonical_results == (passing_rank_1, wait_rank_2, buy_rank_3)


def test_adapter_uses_rank_when_business_decision_is_equal():
    first = _analysis(rank=2, score=100.0, decision=TradingPathDecision.WAIT)
    second = _analysis(rank=1, hypothesis="RANGE_BREAK", score=1.0, decision=TradingPathDecision.WAIT)
    view = CanonicalOpportunityAnalysisV015.from_analyses([first, second])

    assert view.best_analysis is second


def test_adapter_quality_gate_uses_canonical_v015_result_when_present():
    analysis = _analysis(rank=1, quality_gate_passed=False)
    view = CanonicalOpportunityAnalysisV015.from_analyses([analysis])

    assert view.strategies[0].quality_gate is False


def test_adapter_empty_result_is_safe():
    view = CanonicalOpportunityAnalysisV015.from_analyses([])

    assert view.best_analysis is None
    assert view.market_regime is None
    assert view.confidence is None
    assert view.opportunity is None
    assert view.strategies == ()
