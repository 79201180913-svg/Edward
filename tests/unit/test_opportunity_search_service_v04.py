from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import AnalysisResult, Candle, StrategyResult
from edward.services.opportunity_search_service import OpportunitySearchResult, OpportunitySearchService


def _strategy(name: str, score: float, quality: bool) -> StrategyResult:
    return StrategyResult(
        strategy=name,
        parameters={"lookback": 20},
        return_pct=10.0,
        max_drawdown_pct=5.0,
        sharpe=1.0,
        trades=20,
        stability=70.0,
        quality_gate=quality,
        score=score,
        test_score=score - 1.0,
    )


def _analysis(strategies: list[StrategyResult]) -> AnalysisResult:
    return AnalysisResult(
        instrument_uid="uid-1",
        ticker="TEST",
        profile="medium_term",
        risk_profile="balanced",
        horizon="medium",
        market_regime="Trend",
        recommendation=None,
        confidence="High",
        score=max((item.score for item in strategies), default=0.0),
        strategies=strategies,
        explanation="",
        created_at="2026-08-25T00:00:00+00:00",
    )


def test_best_strategy_prefers_quality_gate_then_score():
    strategies = [_strategy("A", 95.0, False), _strategy("B", 70.0, True), _strategy("C", 80.0, True)]
    selected = OpportunitySearchService._best_strategy(strategies)
    assert selected is not None
    assert selected.strategy == "C"


def test_best_strategy_uses_score_as_fallback_when_all_fail():
    strategies = [_strategy("A", 41.0, False), _strategy("B", 55.0, False), _strategy("C", 37.0, False)]
    selected = OpportunitySearchService._best_strategy(strategies)
    assert selected is not None
    assert selected.strategy == "B"
    assert selected.quality_gate is False


def test_scan_ranks_buy_before_wait_before_pass(monkeypatch):
    service = OpportunitySearchService.__new__(OpportunitySearchService)
    service._active_account = lambda: None

    class FakeCatalog:
        def list(self, *_args, **_kwargs):
            return [{"uid": "1", "ticker": "A", "name": "A", "last_price": "1"}, {"uid": "2", "ticker": "B", "name": "B", "last_price": "2"}, {"uid": "3", "ticker": "C", "name": "C", "last_price": "3"}]

    service.catalog = FakeCatalog()
    ordered = [
        OpportunitySearchResult("2", "B", "B", 2.0, "Trend", "Momentum", 75.0, 82.0, "BUY", "VALID", "BUY_CONDITIONS_MET", "", 0),
        OpportunitySearchResult("1", "A", "A", 1.0, "Trend", "Breakout", 70.0, 55.0, "WAIT", "VALID", "OPPORTUNITY_BELOW_BUY_THRESHOLD", "", 0),
        OpportunitySearchResult("3", "C", "C", 3.0, None, "Mean Reversion", 30.0, 0.0, "PASS", "VALID", "STRATEGY_QUALITY_FAIL", "", 0),
    ]
    values = iter(ordered)
    service._evaluate_instrument = lambda **_kwargs: next(values)

    results = service.scan(profile="medium_term", instrument_kind="SHARE")
    assert [item.ticker for item in results] == ["B", "A", "C"]
    assert [item.decision for item in results] == ["BUY", "WAIT", "PASS"]


def test_unavailable_result_keeps_instrument_identity():
    result = OpportunitySearchService._unavailable(
        {"uid": "uid-9", "ticker": "TEST", "name": "Test"},
        12.5,
        7.0,
        "Недостаточно исторических данных для анализа.",
    )
    assert result.instrument_uid == "uid-9"
    assert result.ticker == "TEST"
    assert result.status == "ANALYSIS_UNAVAILABLE"
    assert result.decision is None
    assert result.quantity == 7.0


def test_analysis_helper_candles_are_normalized():
    service = OpportunitySearchService.__new__(OpportunitySearchService)
    service.client = None
    service.catalog = None
    service.analysis = None
    payload = {
        "candles": [
            {
                "time": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
                "open": {"units": "10", "nano": 0},
                "high": {"units": "11", "nano": 0},
                "low": {"units": "9", "nano": 0},
                "close": {"units": "10", "nano": 0},
                "volume": 100,
            }
        ]
    }
    service.client = type("Client", (), {"get_candles": lambda self, *_args, **_kwargs: payload})()
    candles = service._get_candles("uid")
    assert len(candles) == 1
    assert isinstance(candles[0], Candle)
    assert candles[0].close == 10.0
