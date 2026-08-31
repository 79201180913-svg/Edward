from __future__ import annotations

from types import SimpleNamespace

from edward.services.opportunity_search_service import OpportunitySearchResult
from edward.services.opportunity_search_service_live_v04 import LiveOpportunitySearchService


def _result(ticker: str) -> OpportunitySearchResult:
    return OpportunitySearchResult(
        instrument_uid=ticker,
        ticker=ticker,
        name=ticker,
        price=1.0,
        market_regime="Trend",
        strategy_name="Momentum",
        strategy_score=70.0,
        opportunity_score=80.0,
        decision="WAIT",
        status="VALID",
        reason="WAIT",
        explanation="",
        quantity=0,
    )


def _candles() -> list[dict[str, object]]:
    return [
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


def test_scan_calculates_analysis_once_and_hands_same_result_to_opportunity():
    service = LiveOpportunitySearchService.__new__(LiveOpportunitySearchService)
    service._active_account = lambda: None
    service._provided_candles = {}

    calls: list[dict[str, object]] = []
    canonical_result = SimpleNamespace(trading_path_research={"status": "READY"})

    class FakePipeline:
        def analyze(self, **kwargs):
            calls.append(kwargs)
            return canonical_result

        def force_recompute(self):
            return None

    service.analysis_pipeline = FakePipeline()

    class FakeClient:
        def get_candles(self, *_args, **_kwargs):
            return {"candles": _candles()}

    service.client = FakeClient()
    service.catalog = SimpleNamespace(
        list=lambda *_args, **_kwargs: [
            {
                "uid": "1",
                "ticker": "A",
                "name": "A",
                "last_price": "1",
                "buy_available": True,
                "trading_available": True,
            }
        ]
    )
    service._forecast_quality_gate = lambda *_args, **_kwargs: (False, "НЕ ПРИМЕНИМ")

    observed: list[object] = []

    def fake_evaluate(**_kwargs):
        observed.append(service.analysis.result)
        return _result("A")

    service._evaluate_instrument = fake_evaluate

    results = service.scan(profile="medium_term", instrument_kind="SHARE", scope="MARKET")

    assert len(calls) == 1
    assert calls[0]["instrument_uid"] == "1"
    assert len(observed) == 1
    assert observed[0] is canonical_result
    assert canonical_result.trading_path_research == {"status": "READY"}
    assert len(results) == 1
