from datetime import datetime, timezone
from types import SimpleNamespace

from edward.domain import (
    TradingPathAnalysisStatus,
    TradingPathAnalysisV012,
    TradingPathCandidate,
    TradingPathCurrentState,
    TradingPathDecision,
    TradingPathEvidence,
    TradingPathOpportunity,
    TradingPathRule,
)
from edward.services.trading_path_market_context_service_v012 import TradingPathMarketContextServiceV012


def _path(hypothesis: str, rank: int) -> TradingPathAnalysisV012:
    return TradingPathAnalysisV012(
        instrument_uid="uid-1",
        ticker="SBER",
        strategy_family="Breakout" if hypothesis == "BREAKOUT_EXPANSION" else "Momentum",
        hypothesis=hypothesis,
        regime="TREND_UP",
        volatility_bucket="Normal",
        direction="Positive",
        horizon=5,
        evidence=SimpleNamespace(),
        opportunity=TradingPathOpportunity(),
        current_state=TradingPathCurrentState.WAIT,
        decision=TradingPathDecision.WAIT,
        status=TradingPathAnalysisStatus.VALIDATED,
        rank=rank,
    )


def _candidate(hypothesis: str) -> TradingPathCandidate:
    return TradingPathCandidate(
        rule=TradingPathRule(
            instrument_uid="uid-1",
            ticker="SBER",
            hypothesis=hypothesis,
            regime="TREND_UP",
            volatility_bucket="Normal",
            direction="Positive",
            horizon=5,
        ),
        evidence=TradingPathEvidence(
            observations=20,
            mean_forward_return_pct=1.0,
            median_forward_return_pct=0.8,
            win_rate_pct=60.0,
            baseline_mean_return_pct=0.2,
            excess_return_pct=0.8,
            sufficient_sample=True,
        ),
    )


def _snapshot():
    regime = SimpleNamespace(result=SimpleNamespace(strategy_compatibility={"Breakout": 80.0, "Momentum": 40.0}))
    relative = SimpleNamespace(excess_return_pct=2.0, classification="OUTPERFORMING")
    volatility = SimpleNamespace(classification="LOWER_THAN_MARKET")
    return SimpleNamespace(
        context_status="FULL",
        benchmark_id="IMOEX",
        market_regime=regime,
        relative_strength=relative,
        volatility=volatility,
        as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_context_service_populates_snapshot_components_without_changing_decision():
    paths = (_path("BREAKOUT_EXPANSION", 1), _path("IMPULSE_CONTINUATION", 2))
    candidates = (_candidate("BREAKOUT_EXPANSION"), _candidate("IMPULSE_CONTINUATION"))

    result = TradingPathMarketContextServiceV012.apply(paths, candidates, _snapshot())

    assert len(result) == 2
    assert result[0].market_context.benchmark_id == "IMOEX"
    assert result[0].market_context.context_adjusted_score is not None
    assert result[0].market_context.rank_delta is not None
    assert all(item.decision is TradingPathDecision.WAIT for item in result)
    assert all(item.status is TradingPathAnalysisStatus.VALIDATED for item in result)


def test_context_unavailable_is_non_blocking():
    paths = (_path("BREAKOUT_EXPANSION", 1),)
    candidates = (_candidate("BREAKOUT_EXPANSION"),)
    snapshot = SimpleNamespace(context_status="UNAVAILABLE")

    result = TradingPathMarketContextServiceV012.apply(paths, candidates, snapshot)

    assert result == paths
