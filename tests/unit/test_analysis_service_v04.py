from __future__ import annotations

from datetime import datetime, timedelta, timezone

from edward.services.analysis_service import AnalysisService, Candle
from edward.storage.analysis_repository import AnalysisSnapshotRepository
from edward.storage.sqlite_store import SQLiteStore


def _candles(count: int = 900) -> list[Candle]:
    result: list[Candle] = []
    price = 100.0
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    for index in range(count):
        if index < 300:
            drift = 0.0015
        elif index < 600:
            drift = -0.0008
        else:
            drift = 0.0012
        price *= 1.0 + drift
        result.append(Candle(start + timedelta(days=index), price * 0.998, price * 1.01, price * 0.99, price, 1000 + index))
    return result


def test_analysis_returns_all_strategies_and_version():
    result = AnalysisService().analyze(
        instrument_uid="uid-1",
        ticker="TEST",
        candles=_candles(),
        profile="medium_term",
    )

    assert result.analysis_version == "0.4.0"
    assert result.market_regime in {"Trend", "Momentum", "Range", "Unclear"}
    assert len(result.strategies) == 4
    assert {item.strategy for item in result.strategies} == {
        "Trend Following",
        "Momentum",
        "Breakout",
        "Mean Reversion",
    }
    assert 0 <= result.score <= 100


def test_walk_forward_uses_component_stability():
    result = AnalysisService().analyze(
        instrument_uid="uid-stability",
        ticker="TEST-STABILITY",
        candles=_candles(),
        profile="medium_term",
    )

    for strategy in result.strategies:
        assert strategy.wf_windows >= 5
        assert 0 <= strategy.positive_return_windows <= strategy.wf_windows
        assert 0 <= strategy.risk_ok_windows <= strategy.wf_windows
        assert 0 <= strategy.positive_sharpe_windows <= strategy.wf_windows
        assert 0 <= strategy.return_consistency <= 100
        assert 0 <= strategy.risk_consistency <= 100
        assert 0 <= strategy.sharpe_consistency <= 100
        expected_stability = round(
            strategy.return_consistency * 0.50
            + strategy.risk_consistency * 0.30
            + strategy.sharpe_consistency * 0.20,
            2,
        )
        assert strategy.stability == expected_stability


def test_score_is_normalized_and_uses_new_weights():
    service = AnalysisService()

    score = service._score(
        return_pct=15.0,
        drawdown_pct=0.0,
        sharpe=2.0,
        trades=10,
        stability_pct=100.0,
        return_target_pct=15.0,
        drawdown_limit_pct=25.0,
    )

    assert score == 100.0

    lower_score = service._score(
        return_pct=7.5,
        drawdown_pct=12.5,
        sharpe=1.0,
        trades=10,
        stability_pct=50.0,
        return_target_pct=15.0,
        drawdown_limit_pct=25.0,
    )
    assert 0 < lower_score < 100


def test_quality_gate_depends_on_profile_thresholds():
    service = AnalysisService()
    assert service._profile_params("long_term")["max_drawdown_pct"] == 30.0
    assert service._profile_params("medium_term")["max_drawdown_pct"] == 25.0
    assert service._profile_params("speculative")["max_drawdown_pct"] == 35.0
    assert service._profile_params("long_term")["min_stability_pct"] == 60.0
    assert service._profile_params("medium_term")["min_stability_pct"] == 60.0
    assert service._profile_params("speculative")["min_stability_pct"] == 55.0


def test_analysis_is_saved_to_sqlite(tmp_path):
    store = SQLiteStore(tmp_path)
    service = AnalysisService(store)
    result = service.analyze(
        instrument_uid="uid-2",
        ticker="TEST2",
        candles=_candles(),
        profile="long_term",
    )

    run_id = service.save(result)
    snapshot_id = AnalysisSnapshotRepository(store).save(result, run_id)

    assert run_id is None or run_id > 0
    assert snapshot_id > 0
    latest = AnalysisSnapshotRepository(store).latest("uid-2", "long_term", "balanced")
    assert latest is not None
    assert latest["ticker"] == "TEST2"
    assert latest["strategy"] == result.recommendation


def test_insufficient_history_is_rejected():
    try:
        AnalysisService().analyze(
            instrument_uid="uid-3",
            ticker="TEST3",
            candles=_candles(149),
        )
    except ValueError as exc:
        assert "150" in str(exc)
    else:
        raise AssertionError("Analysis must reject history shorter than 150 candles")
