from types import SimpleNamespace

from edward.services.analysis_service import StrategyResult
from edward.services.decision_engine import (
    Decision,
    DecisionEngine,
    DecisionResult,
    DecisionStatus,
    InstrumentContextData,
    MarketContextData,
    OpportunityContext,
    PortfolioContextData,
    PositionContextData,
    RiskContextData,
    Scenario,
    StrategyContextData,
)
from edward.services.opportunity_engine import OpportunityEngine
from edward.services.opportunity_search_service import OpportunitySearchService


def _strategy() -> StrategyResult:
    return StrategyResult(
        strategy="Momentum",
        parameters={"lookback": 20},
        return_pct=10.0,
        max_drawdown_pct=5.0,
        sharpe=1.0,
        trades=20,
        stability=70.0,
        quality_gate=True,
        score=80.0,
        test_score=75.0,
    )


def _prepare_service(monkeypatch, *, position_quantity: float):
    service = OpportunitySearchService.__new__(OpportunitySearchService)
    service.analysis = SimpleNamespace(
        analyze=lambda **_: SimpleNamespace(
            market_regime="Trend",
            confidence="High",
            strategies=[_strategy()],
        )
    )
    service.instrument_context = SimpleNamespace(
        build=lambda instrument, trading_status: InstrumentContextData(
            instrument_uid=instrument["uid"],
            ticker=instrument["ticker"],
            buy_available=True,
            sell_available=True,
            trading_status=trading_status,
            available=True,
        )
    )
    service.market_context = SimpleNamespace(
        build=lambda **_: MarketContextData(
            current_price=100.0,
            market_regime="Trend",
            regime_compatible=True,
            entry_ok=True,
            available=True,
        )
    )
    service.portfolio_context = SimpleNamespace(
        build=lambda **_: SimpleNamespace(
            portfolio=PortfolioContextData(
                portfolio_value=100000.0,
                available_cash=50000.0,
                available=True,
                allows_buy=position_quantity == 0,
                allows_add=position_quantity > 0,
            ),
            position=PositionContextData(
                quantity=position_quantity,
                portfolio_weight_pct=5.0 if position_quantity else 0.0,
                target_weight_pct=10.0,
            ),
        )
    )
    service._get_candles = lambda _uid: [object()] * 150

    monkeypatch.setattr(
        OpportunityEngine,
        "evaluate",
        staticmethod(
            lambda *_args, **_kwargs: SimpleNamespace(
                context=OpportunityContext(
                    opportunity_score=80.0,
                    entry_ok=True,
                    risk_ok=True,
                    strategy_ok=True,
                    market_regime_compatible=True,
                ),
                explanation="OK",
            )
        ),
    )
    captured = {}

    def evaluate(request):
        captured["request"] = request
        return DecisionResult(
            decision=Decision.HOLD if position_quantity else Decision.BUY,
            status=DecisionStatus.VALID,
            reason_codes=("TEST",),
            explanation="OK",
            strategy_name="Momentum",
            strategy_score=80.0,
            opportunity_score=80.0,
        )

    monkeypatch.setattr(DecisionEngine, "evaluate", staticmethod(evaluate))
    return service, captured


def test_portfolio_position_uses_open_position_decision_branch(monkeypatch):
    service, captured = _prepare_service(monkeypatch, position_quantity=100)

    service._evaluate_instrument(
        instrument={"uid": "uid-1", "ticker": "TEST", "name": "Test", "last_price": "100"},
        profile="medium_term",
        positions={"securities": []},
        portfolio={},
    )

    assert captured["request"].scenario == Scenario.SINGLE_INSTRUMENT
    assert captured["request"].position.is_open is True


def test_market_instrument_uses_new_position_decision_branch(monkeypatch):
    service, captured = _prepare_service(monkeypatch, position_quantity=0)

    service._evaluate_instrument(
        instrument={"uid": "uid-2", "ticker": "NEW", "name": "New", "last_price": "100"},
        profile="medium_term",
        positions=None,
        portfolio=None,
    )

    assert captured["request"].scenario == Scenario.OPPORTUNITY_SEARCH
    assert captured["request"].position.is_open is False
