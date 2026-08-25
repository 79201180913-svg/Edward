from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import AnalysisResult, Candle, StrategyResult
from edward.services.opportunity_search_service import OpportunitySearchResult, OpportunitySearchService, MARKET_SCOPE, PORTFOLIO_SCOPE


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


def _buyable_instrument(uid: str, ticker: str, price: str) -> dict[str, object]:
    return {
        "uid": uid,
        "ticker": ticker,
        "name": ticker,
        "last_price": price,
        "buy_available": True,
        "trading_available": True,
    }


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
            return [
                _buyable_instrument("1", "A", "1"),
                _buyable_instrument("2", "B", "2"),
                _buyable_instrument("3", "C", "3"),
            ]

    service.catalog = FakeCatalog()
    ordered = [
        OpportunitySearchResult("2", "B", "B", 2.0, "Trend", "Momentum", 75.0, 82.0, "BUY", "VALID", "BUY_CONDITIONS_MET", "", 0),
        OpportunitySearchResult("1", "A", "A", 1.0, "Trend", "Breakout", 70.0, 55.0, "WAIT", "VALID", "OPPORTUNITY_BELOW_BUY_THRESHOLD", "", 0),
        OpportunitySearchResult("3", "C", "C", 3.0, None, "Mean Reversion", 30.0, 0.0, "PASS", "VALID", "STRATEGY_QUALITY_FAIL", "", 0),
    ]
    values = iter(ordered)
    service._evaluate_instrument = lambda **_kwargs: next(values)

    results = service.scan(profile="medium_term", instrument_kind="SHARE", scope=MARKET_SCOPE)
    assert [item.ticker for item in results] == ["B", "A", "C"]
    assert [item.decision for item in results] == ["BUY", "WAIT", "PASS"]


def test_market_universe_contains_only_buyable_tradeable_instruments():
    service = OpportunitySearchService.__new__(OpportunitySearchService)

    class FakeCatalog:
        def list(self, *_args, **_kwargs):
            return [
                {"uid": "buy", "ticker": "BUY", "buy_available": True, "trading_available": True},
                {"uid": "sell", "ticker": "SELL", "buy_available": False, "sell_available": True, "trading_available": True},
                {"uid": "closed", "ticker": "CLOSED", "buy_available": True, "trading_available": False},
            ]

    service.catalog = FakeCatalog()
    result = service._market_universe("SHARE")
    assert [item["ticker"] for item in result] == ["BUY"]


def test_portfolio_universe_contains_only_held_positions():
    service = OpportunitySearchService.__new__(OpportunitySearchService)

    class FakeCatalog:
        def list(self, *_args, **_kwargs):
            return [
                {"uid": "held", "ticker": "HELD", "name": "Held"},
                {"uid": "other", "ticker": "OTHER", "name": "Other"},
            ]

    service.catalog = FakeCatalog()
    positions = {
        "securities": [
            {"instrument_uid": "held", "ticker": "HELD", "balance": 10},
            {"instrument_uid": "zero", "ticker": "ZERO", "balance": 0},
        ]
    }
    result = service._portfolio_universe("SHARE", positions)
    assert [item["ticker"] for item in result] == ["HELD"]


def test_active_account_accepts_sandbox_status_code_two():
    service = OpportunitySearchService.__new__(OpportunitySearchService)

    class FakeClient:
        def get_accounts(self):
            return {"accounts": [{"id": "sandbox-1", "status": "2"}]}

    service.client = FakeClient()
    assert service._active_account() == "sandbox-1"


def test_scan_reports_staged_progress():
    service = OpportunitySearchService.__new__(OpportunitySearchService)
    service._active_account = lambda: None

    class FakeCatalog:
        def list(self, *_args, **_kwargs):
            return [_buyable_instrument("1", "A", "1")]

    service.catalog = FakeCatalog()
    service._evaluate_instrument = lambda **_kwargs: OpportunitySearchResult(
        "1", "A", "A", 1.0, "Trend", "Momentum", 75.0, 82.0, "BUY", "VALID", "BUY_CONDITIONS_MET", "", 0
    )
    events: list[tuple[str, float, int, int]] = []

    results = service.scan(
        profile="medium_term",
        instrument_kind="SHARE",
        scope=MARKET_SCOPE,
        progress_callback=lambda stage, percent, current, total: events.append((stage, percent, current, total)),
    )

    stages = [stage for stage, *_ in events]
    assert results[0].ticker == "A"
    assert "Загрузка списка инструментов" in stages
    assert any(stage.startswith("Вселенная анализа:") for stage in stages)
    assert "Portfolio Context загружен" in stages
    assert any(stage.startswith("Market Data:") for stage in stages)
    assert "Ранжирование возможностей" in stages
    assert stages[-1] == "Сканирование завершено"
    assert events[-1][1] == 100.0


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
