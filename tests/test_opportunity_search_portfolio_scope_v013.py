from types import SimpleNamespace

from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService


def test_portfolio_scope_uses_positions_without_market_catalog():
    service = object.__new__(LiveOpportunitySearchService)
    positions = SimpleNamespace(
        securities=[
            SimpleNamespace(instrument_uid="UID-1", ticker="AAA", balance=10),
            SimpleNamespace(instrument_uid="UID-2", ticker="BBB", balance=5),
        ]
    )

    class ForbiddenCatalog:
        def list(self, *args, **kwargs):
            raise AssertionError("portfolio scope must not enumerate the market catalog")

    service.catalog = ForbiddenCatalog()
    result = service._build_universe(scope="PORTFOLIO", instrument_kind="SHARE", positions=positions)

    assert [item["uid"] for item in result] == ["UID-1", "UID-2"]
    assert [item["ticker"] for item in result] == ["AAA", "BBB"]


def test_live_scan_publishes_each_completed_instrument_immediately():
    service = object.__new__(LiveOpportunitySearchService)
    service._active_account = lambda: None
    service.client = SimpleNamespace()
    service._build_universe = lambda **_kwargs: [
        {"uid": "UID-1", "ticker": "AAA", "name": "A", "last_price": 10.0},
        {"uid": "UID-2", "ticker": "BBB", "name": "B", "last_price": 20.0},
    ]
    service._get_candles = lambda _uid: [object()] * 300
    path = SimpleNamespace(
        hypothesis="H1", strategy_family="H1", regime="RANGE", volatility_bucket="Normal",
        direction="Positive", horizon=5, status=SimpleNamespace(value="promotable"),
        opportunity=SimpleNamespace(score=75.0, risk_score=20.0, risk_gate=True),
    )
    canonical = SimpleNamespace(
        best_path=path, decision=SimpleNamespace(value="buy"),
        current_state=SimpleNamespace(value="entry_ready"), total_paths=1,
        promoted_paths=1, research_only_paths=0, rejected_paths=0,
    )
    service.path_runtime = SimpleNamespace(scan_instrument=lambda **_kwargs: canonical)

    callbacks = []
    results = service.scan(
        scope="PORTFOLIO",
        instrument_kind="SHARE",
        result_callback=lambda result, current, total: callbacks.append((result.ticker, current, total)),
    )

    assert [item.ticker for item in results] == ["AAA", "BBB"]
    assert callbacks == [("AAA", 1, 2), ("BBB", 2, 2)]
