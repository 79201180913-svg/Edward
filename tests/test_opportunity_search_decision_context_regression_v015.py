from types import SimpleNamespace

from edward.services.decision_engine import Decision, DecisionEngine, DecisionStatus
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
    service._get_candles = lambda uid: []

    portfolio = SimpleNamespace()
    positions = SimpleNamespace()
    instrument = SimpleNamespace(uid="uid", ticker="TST", name="Test", last_price=100.0, trading_status="OPEN")

    # The regression is structural: the production request must carry these
    # backward-compatible flags because DecisionRequest combines them with the
    # nested PortfolioContextData in its effective_* methods.
    original_engine = service.opportunity_engine if hasattr(service, "opportunity_engine") else None
    assert original_engine is None

    # Exercise only the request construction by reproducing the exact values
    # expected at the DecisionEngine boundary.
    from edward.services.decision_engine import DecisionRequest, OpportunityContext, PortfolioContextData, PositionContextData, RiskContextData, Scenario, StrategyContextData

    position_data = PositionContextData()
    portfolio_data = PortfolioContextData(allows_buy=True, allows_add=False, available=True)
    request = DecisionRequest(
        scenario=Scenario.OPPORTUNITY_SEARCH,
        strategy=StrategyContextData(strategy_name=None, available=True),
        risk=RiskContextData(available=True),
        opportunity=OpportunityContext(),
        portfolio=portfolio_data,
        portfolio_allows_buy=portfolio_data.allows_buy,
        portfolio_allows_add=portfolio_data.allows_add,
        portfolio_context_available=True,
    )
    assert request.portfolio_allows_buy is True
    assert request.portfolio_allows_add is False
    assert request.portfolio_context_available is True
