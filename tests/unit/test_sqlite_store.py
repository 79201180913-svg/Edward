from pathlib import Path

from edward.storage.sqlite_store import SQLiteStore


def test_store_creates_database_and_tables(tmp_path: Path):
    store = SQLiteStore(tmp_path)
    assert store.db_path == tmp_path / "edward.db"
    assert store.db_path.exists()

    with store._connect() as connection:
        names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert {"walk_forward_runs", "analysis_snapshots"}.issubset(names)


def test_store_saves_and_reads_latest_accepted_walk_forward(tmp_path: Path):
    store = SQLiteStore(tmp_path)
    first_id = store.save_walk_forward(
        instrument_uid="A",
        ticker="SBER",
        profile="SWING",
        risk_profile="MODERATE",
        strategy="TREND_FOLLOWING",
        strategy_version="0.4.0",
        status="ACCEPTED",
        created_at="2026-08-25T10:00:00+03:00",
        parameters={"atr_period": 14},
        metrics={"sharpe": 1.2},
    )
    second_id = store.save_walk_forward(
        instrument_uid="A",
        ticker="SBER",
        profile="SWING",
        risk_profile="MODERATE",
        strategy="TREND_FOLLOWING",
        strategy_version="0.4.0",
        status="ACCEPTED",
        created_at="2026-08-25T11:00:00+03:00",
        parameters={"atr_period": 21},
        metrics={"sharpe": 1.4},
    )

    result = store.latest_walk_forward(
        instrument_uid="A",
        profile="SWING",
        risk_profile="MODERATE",
        strategy="TREND_FOLLOWING",
    )

    assert first_id < second_id
    assert result is not None
    assert result["id"] == second_id
    assert result["ticker"] == "SBER"
    assert result["status"] == "ACCEPTED"
    assert result["metrics_json"] == '{"sharpe": 1.4}'


def test_store_does_not_return_rejected_run_when_accepted_only(tmp_path: Path):
    store = SQLiteStore(tmp_path)
    store.save_walk_forward(
        instrument_uid="A",
        ticker="SBER",
        profile="SWING",
        risk_profile="MODERATE",
        strategy="BREAKOUT",
        strategy_version="0.4.0",
        status="REJECTED",
        created_at="2026-08-25T12:00:00+03:00",
    )

    assert store.latest_walk_forward(
        instrument_uid="A",
        profile="SWING",
        risk_profile="MODERATE",
        strategy="BREAKOUT",
        accepted_only=True,
    ) is None
