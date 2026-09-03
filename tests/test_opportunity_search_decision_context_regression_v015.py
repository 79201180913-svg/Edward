from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.analysis_service import Candle, StrategyResult
from edward.services.decision_engine import Decision, DecisionEngine, DecisionStatus, OpportunityContext
from edward.services.opportunity_search_service import OpportunitySearchService


def test_opportunity_search_passes_portfolio_decision_flags(monkeypatch):
    captured = {}

    def evaluate(request):
        captured["request"] = request
        return SimpleNamespace(
            decision=Decision.WAIT,
            status=DecisionStatus.VALID,
            reason_codes=(),
            explanation="test",
            execution_ready=False,
        )

    monkeypatch.setattr(DecisionEngine, "evaluate", staticmethod(evaluate))

    candles = tuple(
        Candle(
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=index),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0 + index * 0.01,
            volume=1000.0,
        )
        for index in range(150)
    )
    selected = StrategyResult(
        strategy="test",
        parameters={},
        return_pct=10.0,
        sharpe=1.0,
        trades=10,
        score=1.0,
        quality_gate=True,
        test_score=0.8,
        stability=0.9,
        max_drawdown_pct=5.0,
    )
    analysis = SimpleNamespace(
        strategies=[selected],
        market_regime="TREND_UP",
        confidence="HIGH",
        best_analysis=None,
    )

    service = OpportunitySearchService.__new__(OpportunitySearchService)
    service.instrument_context = SimpleNamespace(build=lambda instrument, status: SimpleNamespace(available=True))
    service.market_context = SimpleNamespace(build=lambda **kwargs: SimpleNamespace(available=True, current_price=100.0))
    service.portfolio_context = SimpleNamespace(
        build=lambda **kwargs: SimpleNamespace(
            position=SimpleNamespace(quantity=0, is_open=False, portfolio_weight_pct=0.0, target_weight_pct=5.0),
            portfolio=SimpleNamespace(
                portfolio_value=100000.0,
                available_cash=50000.0,
                blocked_cash=0.0,
                current_weight_pct=0.0,
                target_weight_pct=5.0,
                max_position_weight_pct=10.0,
                allows_buy=True,
                allows_add=False,
                available=True,
            ),
        )
    )
    service.opportunity_engine = SimpleNamespace(
        evaluate=lambda *args, **kwargs: SimpleNamespace(
            context=OpportunityContext(
                opportunity_score=80.0,
                entry_ok=True,
                risk_ok=True,
                strategy_ok=True,
                market_regime_compatible=True,
                critical_risk=False,
            ),
            risk=SimpleNamespace(score=10.0),
        )
    )
    service.analysis = SimpleNamespace(analyze=lambda **kwargs: analysis)
    service._get_candles = lambda uid: list(candles)
    service._benchmark_context = lambda instrument, candles: (None, None)
    service._trade_plan = lambda *args, **kwargs: None
    service._position_size = lambda *args, **kwargs: (0, 0.0, 0.0)

    instrument = SimpleNamespace(uid="uid", ticker="TST", name="Test", last_price=100.0, trading_status="OPEN")

    result = service._evaluate_instrument(
        instrument=instrument,
        profile="medium_term",
        positions=SimpleNamespace(),
        portfolio=SimpleNamespace(),
    )

    assert result.status == DecisionStatus.VALID.value
    request = captured["request"]
    assert request.portfolio_allows_buy is True
    assert request.portfolio_allows_add is False
    assert request.portfolio_context_available is True
