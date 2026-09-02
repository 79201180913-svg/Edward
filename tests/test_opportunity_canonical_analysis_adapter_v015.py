from datetime import datetime, timedelta, timezone

from edward.domain import TradingPathAnalysisV012, TradingPathAnalysisStatus, TradingPathCurrentState, TradingPathDecision, TradingPathOpportunity, TradingPathValidationSummary
from edward.services.opportunity_canonical_analysis_adapter_v015 import CanonicalOpportunityAnalysisV015


def _analysis(*, rank: int, hypothesis: str = "BREAKOUT_EXPANSION", score: float = 10.0) -> TradingPathAnalysisV012:
    evidence = type("Evidence", (), {"mean_forward_return_pct": 2.5, "max_drawdown_pct": 4.0, "observations": 12})()
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
            robustness_score=80.0,
            positive_oos_windows_pct=100.0,
            statistical_valid=True,
            promotion_status="validated",
        ),
        opportunity=TradingPathOpportunity(score=score, confidence=0.75, expected_value_pct=2.0, risk_score=20.0, risk_gate=True),
        current_state=TradingPathCurrentState.ENTRY_READY,
        decision=TradingPathDecision.BUY,
        status=TradingPathAnalysisStatus.VALIDATED,
        rank=rank,
    )


def test_adapter_exposes_canonical_best_result_and_legacy_strategy_shape():
    analysis = _analysis(rank=1, hypothesis="ADAPTIVE_RULE:regime=TREND_DOWN AND distance_to_low_20 <= 0.04")
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


def test_adapter_preserves_rank_order_for_best_analysis():
    first = _analysis(rank=2, score=100.0)
    second = _analysis(rank=1, hypothesis="RANGE_BREAK", score=1.0)
    view = CanonicalOpportunityAnalysisV015.from_analyses([first, second])

    assert view.best_analysis is second
    assert view.canonical_results == (first, second)


def test_adapter_empty_result_is_safe():
    view = CanonicalOpportunityAnalysisV015.from_analyses([])

    assert view.best_analysis is None
    assert view.market_regime is None
    assert view.confidence is None
    assert view.opportunity is None
    assert view.strategies == ()
