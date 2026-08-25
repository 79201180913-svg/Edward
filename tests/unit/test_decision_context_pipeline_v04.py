from types import SimpleNamespace

from edward.services.opportunity_engine import OpportunityEngine
import edward.ui.decision_context_ui_v04 as decision_context_ui_v04


def test_analysis_context_pipeline_forwards_risk_portfolio_kwargs(monkeypatch):
    captured = {}

    def fake_evaluate(analysis, candles, strategy_result, **kwargs):
        captured["kwargs"] = kwargs
        captured["strategy_result"] = strategy_result
        return SimpleNamespace(
            context=SimpleNamespace(
                entry_ok=True,
                risk_ok=True,
                critical_risk=False,
            )
        )

    original_evaluate = OpportunityEngine.evaluate
    original_builder = decision_context_ui_v04._field

    monkeypatch.setattr(OpportunityEngine, "evaluate", classmethod(lambda _cls, *args, **kwargs: fake_evaluate(*args, **kwargs)))
    monkeypatch.setattr(decision_context_ui_v04, "_field", original_builder)
    monkeypatch.setattr(decision_context_ui_v04, "_decision_context_pipeline_v04_installed", False)

    try:
        decision_context_ui_v04._install_analysis_context_pipeline()
        OpportunityEngine.evaluate(
            SimpleNamespace(strategies=[]),
            [],
            None,
            position_weight_pct=5.0,
            target_weight_pct=10.0,
            max_position_weight_pct=20.0,
            portfolio_available=True,
            available_cash=50000.0,
            estimated_trade_value=5000.0,
        )
    finally:
        OpportunityEngine.evaluate = original_evaluate
        decision_context_ui_v04._decision_context_pipeline_v04_installed = False

    assert captured["strategy_result"] is None
    assert captured["kwargs"] == {
        "position_weight_pct": 5.0,
        "target_weight_pct": 10.0,
        "max_position_weight_pct": 20.0,
        "portfolio_available": True,
        "available_cash": 50000.0,
        "estimated_trade_value": 5000.0,
    }
