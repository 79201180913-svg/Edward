from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineV08Result
from edward.services.decision_engine import OpportunityContext
from edward.services.multifactor_analysis_service_v081 import MultiFactorAnalysisServiceV081
from edward.services.multifactor_overlay_service_v081 import MultiFactorOverlayServiceV081, PointInTimeGuardV081
from edward.services.opportunity_engine import OpportunityResult


def _pipeline(score=60.0, confidence=40.0, entry_signal=True):
    context = OpportunityContext(
        opportunity_score=score,
        entry_ok=entry_signal,
        risk_ok=True,
        strategy_ok=True,
        market_regime_compatible=True,
        critical_risk=False,
    )
    opportunity = OpportunityResult(
        context=context,
        score=score,
        entry_signal=entry_signal,
        market_regime_compatible=True,
        explanation="base",
        risk=None,
    )
    confidence_result = SimpleNamespace(overall_confidence=confidence)
    return AnalysisPipelineV08Result(
        analysis=None,
        opportunity=opportunity,
        expected_value=None,
        portfolio_impact=None,
        confidence=confidence_result,
    )


def test_multifactor_overlay_can_raise_score_for_strong_supporting_evidence():
    factors = MultiFactorAnalysisServiceV081.analyze(
        fundamentals={
            "roe": 20, "roic": 20, "net_margin": 18,
            "revenue_growth": 15, "eps_growth": 18, "ebitda_growth": 15,
            "net_debt_to_ebitda": 0.5, "current_ratio": 2,
            "free_cash_flow": 20_000_000, "pe": 8, "ps": 2, "pb": 1.5,
        },
        order_book={
            "bids": [{"price": 99.9, "quantity": 5000}],
            "asks": [{"price": 100.1, "quantity": 2000}],
        },
        trades=[{"direction": "BUY", "quantity": 5000}, {"direction": "SELL", "quantity": 1000}],
        candles=[
            {"volume": 1000, "volume_buy": 800, "volume_sell": 200},
            {"volume": 1000, "volume_buy": 750, "volume_sell": 250},
        ],
        current_signal={"direction": "BUY"},
        historical_signals=[{"direction": "BUY", "initial_price": 100, "close_price": 110}] * 20,
        session_name="REGULAR",
        risk_data={"dlong_client": 5, "dshort_client": 8, "short_enabled": True},
    )

    adjusted, overlay = MultiFactorOverlayServiceV081.apply(_pipeline(score=55), factors)

    assert adjusted.opportunity.score > 55
    assert overlay.entry_quality_score > 50
    assert overlay.decision_blocked is False


def test_clearing_session_blocks_entry():
    factors = MultiFactorAnalysisServiceV081.analyze(session_name="CLEARING")

    adjusted, overlay = MultiFactorOverlayServiceV081.apply(_pipeline(score=85), factors)

    assert overlay.decision_blocked is True
    assert overlay.block_reason == "TRADING_SESSION_BLOCK"
    assert adjusted.opportunity.score <= 44.9


def test_high_instrument_risk_blocks_entry():
    factors = MultiFactorAnalysisServiceV081.analyze(
        session_name="REGULAR",
        risk_data={"dlong_client": 30, "dshort_client": 35, "short_enabled": False},
    )

    _, overlay = MultiFactorOverlayServiceV081.apply(_pipeline(), factors)

    assert overlay.decision_blocked is True
    assert overlay.block_reason == "INSTRUMENT_RISK_TOO_HIGH"


def test_point_in_time_guard_rejects_future_evidence():
    analysis_at = datetime(2026, 8, 28, tzinfo=timezone.utc)
    future = PointInTimeGuardV081.validate(
        source="report",
        available_at=analysis_at + timedelta(days=1),
        analysis_at=analysis_at,
        identifier="R1",
    )

    assert future is not None
    assert future.source == "report"


def test_point_in_time_filter_keeps_only_visible_records():
    analysis_at = datetime(2026, 8, 28, tzinfo=timezone.utc)
    records = [
        {"id": "old", "created_at": "2026-08-27T10:00:00+00:00"},
        {"id": "future", "created_at": "2026-08-29T10:00:00+00:00"},
    ]

    visible, violations = PointInTimeGuardV081.filter_visible(
        records=records,
        analysis_at=analysis_at,
        source="signal",
    )

    assert [x["id"] for x in visible] == ["old"]
    assert [x["id"] for x in violations] == ["future"]
