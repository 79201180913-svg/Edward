from types import SimpleNamespace

from edward.services.opportunity_search_service import OpportunitySearchResult
from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService


def _result(ticker: str, decision: str) -> OpportunitySearchResult:
    return OpportunitySearchResult(
        instrument_uid=ticker,
        ticker=ticker,
        name=ticker,
        price=1.0,
        market_regime="Trend",
        strategy_name="Momentum",
        strategy_score=70.0,
        opportunity_score=80.0,
        decision=decision,
        status="VALID",
        reason="BUY_CONDITIONS_MET",
        explanation="",
        quantity=0,
    )


def _prepare_scan_service(service: LiveOpportunitySearchService) -> None:
    service.analysis = None
    service.analysis_pipeline = SimpleNamespace(analyze=lambda **_kwargs: object())
    service._provided_candles = {}

    class FakeClient:
        def get_candles(self, *_args, **_kwargs):
            return {
                "candles": [
                    {
                        "time": f"2025-01-{(index % 28) + 1:02d}T00:00:00Z",
                        "open": "1",
                        "high": "1",
                        "low": "1",
                        "close": "1",
                        "volume": 1,
                    }
                    for index in range(150)
                ]
            }

    service.client = FakeClient()
    service._forecast_quality_gate = lambda *_args, **_kwargs: (True, "PASS")


def test_scan_emits_each_result_immediately_before_completion():
    service = LiveOpportunitySearchService.__new__(LiveOpportunitySearchService)
    service._active_account = lambda: None
    _prepare_scan_service(service)

    class FakeCatalog:
        def list(self, *_args, **_kwargs):
            return [
                {"uid": "1", "ticker": "A", "name": "A", "last_price": "1", "buy_available": True, "trading_available": True},
                {"uid": "2", "ticker": "B", "name": "B", "last_price": "2", "buy_available": True, "trading_available": True},
            ]

    service.catalog = FakeCatalog()
    values = iter([_result("A", "BUY"), _result("B", "WAIT")])
    service._evaluate_instrument = lambda **_kwargs: next(values)

    published: list[tuple[str, int, int]] = []
    results = service.scan(
        profile="medium_term",
        instrument_kind="SHARE",
        scope="MARKET",
        result_callback=lambda item, current, total: published.append((item.ticker, current, total)),
    )

    assert published == [("A", 1, 2), ("B", 2, 2)]
    assert [item.ticker for item in results] == ["A", "B"]


def test_result_callback_failure_does_not_break_scan():
    service = LiveOpportunitySearchService.__new__(LiveOpportunitySearchService)
    service._active_account = lambda: None
    _prepare_scan_service(service)

    class FakeCatalog:
        def list(self, *_args, **_kwargs):
            return [{"uid": "1", "ticker": "A", "name": "A", "last_price": "1", "buy_available": True, "trading_available": True}]

    service.catalog = FakeCatalog()
    service._evaluate_instrument = lambda **_kwargs: _result("A", "BUY")

    def fail_callback(*_args):
        raise RuntimeError("UI callback failed")

    results = service.scan(profile="medium_term", instrument_kind="SHARE", scope="MARKET", result_callback=fail_callback)

    assert len(results) == 1
    assert results[0].ticker == "A"
