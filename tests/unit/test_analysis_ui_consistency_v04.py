from edward.services.analysis_service import AnalysisResult, StrategyResult
from edward.ui.analysis_ui_consistency_v04 import select_decision_strategy


def _result(*strategies: StrategyResult) -> AnalysisResult:
    return AnalysisResult(
        instrument_uid="uid",
        ticker="TEST",
        profile="medium_term",
        risk_profile="balanced",
        horizon="medium",
        market_regime="Unclear",
        recommendation=None,
        confidence="Low",
        score=0.0,
        strategies=list(strategies),
        explanation="",
        created_at="2026-08-25T00:00:00+00:00",
    )


def _strategy(name: str, score: float, gate: bool) -> StrategyResult:
    return StrategyResult(
        strategy=name,
        parameters={},
        return_pct=0.0,
        max_drawdown_pct=0.0,
        sharpe=0.0,
        trades=1,
        stability=50.0,
        quality_gate=gate,
        score=score,
    )


def test_selects_best_quality_strategy_when_any_passes():
    result = _result(
        _strategy("Trend Following", 30.0, True),
        _strategy("Momentum", 45.0, True),
        _strategy("Breakout", 90.0, False),
    )

    normalized, selected, fallback = select_decision_strategy(result)

    assert selected is not None
    assert selected.strategy == "Momentum"
    assert fallback is False
    assert normalized.strategies[0].strategy == "Momentum"
    assert normalized.recommendation == "Momentum"
    assert normalized.score == 45.0


def test_selects_best_score_as_fallback_when_all_quality_gates_fail():
    result = _result(
        _strategy("Trend Following", 26.3, False),
        _strategy("Momentum", 41.2, False),
        _strategy("Breakout", 37.2, False),
    )

    normalized, selected, fallback = select_decision_strategy(result)

    assert selected is not None
    assert selected.strategy == "Momentum"
    assert fallback is True
    assert normalized.strategies[0].strategy == "Momentum"
    assert normalized.recommendation == "Momentum (fallback: Quality Gate FAIL)"
    assert normalized.score == 41.2
