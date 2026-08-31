from __future__ import annotations

from types import SimpleNamespace

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineV08Result
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


def _canonical_result() -> AnalysisPipelineV08Result:
    return AnalysisPipelineV08Result(
        analysis=SimpleNamespace(
            recommendation="WAIT",
            score=70.0,
            market_regime="Trend",
            strategies=(),
        ),
        opportunity=SimpleNamespace(score=80.0),
        expected_value=SimpleNamespace(expected_value_pct=3.0),
        portfolio_impact=SimpleNamespace(marginal_risk_pct=0.4),
        forecast_quality_score=82.0,
        regime_confidence=61.0,
        evidence_strategy="Momentum",
        portfolio_context_available=True,
        confidence=SimpleNamespace(overall_confidence=73.0),
        trading_path_research=SimpleNamespace(status="READY"),
        version="0.8.0",
    )


def test_scan_calculates_analysis_once_and_consumes_the_same_canonical_result():
    service = LiveOpportunitySearchService.__new__(LiveOpportunitySearchService)
    service._active_account = lambda: None
    service.analysis = None
    service._provided_candles = {}

    calls: list[dict[str, object]] = []
    canonical_result = _canonical_result()

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
    service._evaluate_instrument = lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("legacy opportunity evaluation must not run")
    )

    results = service.scan(profile="medium_term", instrument_kind="SHARE", scope="MARKET")

    assert len(calls) == 1
    assert calls[0]["instrument_uid"] == "1"
    assert len(results) == 1
    assert results[0].ticker == "A"
    assert results[0].opportunity_score == canonical_result.opportunity.score
    assert results[0].decision == canonical_result.analysis.recommendation


def test_scan_does_not_mutate_legacy_analysis_service_when_consuming_canonical_result():
    service = LiveOpportunitySearchService.__new__(LiveOpportunitySearchService)
    service._active_account = lambda: None
    original_analysis = object()
    service.analysis = original_analysis
    service._provided_candles = {}
    canonical_result = _canonical_result()

    class FakePipeline:
        def analyze(self, **_kwargs):
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
    service._evaluate_instrument = lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("legacy opportunity evaluation must not run")
    )

    results = service.scan(profile="medium_term", instrument_kind="SHARE", scope="MARKET")

    assert len(results) == 1
    assert service.analysis is original_analysis
