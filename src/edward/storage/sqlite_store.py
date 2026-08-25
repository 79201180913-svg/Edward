from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteStore:
    """Small local SQLite repository used by Edward analytics and history services."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "edward.db"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS walk_forward_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instrument_uid TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    risk_profile TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    strategy_version TEXT NOT NULL,
                    data_from TEXT,
                    data_to TEXT,
                    training_period TEXT,
                    validation_period TEXT,
                    out_of_sample_period TEXT,
                    parameters_json TEXT NOT NULL DEFAULT '{}',
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    market_regime TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_wf_lookup
                    ON walk_forward_runs(instrument_uid, profile, risk_profile, strategy, status, created_at);

                CREATE TABLE IF NOT EXISTS analysis_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    instrument_uid TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    risk_profile TEXT NOT NULL,
                    horizon TEXT NOT NULL,
                    strategy TEXT,
                    walk_forward_run_id INTEGER,
                    signal TEXT NOT NULL,
                    confidence REAL,
                    entry_price TEXT,
                    stop_loss TEXT,
                    take_profit TEXT,
                    risk_reward TEXT,
                    market_regime TEXT,
                    explanation_json TEXT NOT NULL DEFAULT '{}',
                    valid_until TEXT,
                    invalidation_conditions_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(walk_forward_run_id) REFERENCES walk_forward_runs(id)
                );

                CREATE INDEX IF NOT EXISTS idx_snapshot_lookup
                    ON analysis_snapshots(instrument_uid, profile, risk_profile, created_at);
                """
            )

    def save_walk_forward(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        profile: str,
        risk_profile: str,
        strategy: str,
        strategy_version: str,
        status: str,
        created_at: str,
        parameters: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        data_from: str | None = None,
        data_to: str | None = None,
        training_period: str | None = None,
        validation_period: str | None = None,
        out_of_sample_period: str | None = None,
        market_regime: str | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO walk_forward_runs (
                    instrument_uid, ticker, profile, risk_profile, strategy,
                    strategy_version, data_from, data_to, training_period,
                    validation_period, out_of_sample_period, parameters_json,
                    metrics_json, market_regime, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instrument_uid,
                    ticker,
                    profile,
                    risk_profile,
                    strategy,
                    strategy_version,
                    data_from,
                    data_to,
                    training_period,
                    validation_period,
                    out_of_sample_period,
                    json.dumps(parameters or {}, ensure_ascii=False, sort_keys=True),
                    json.dumps(metrics or {}, ensure_ascii=False, sort_keys=True),
                    market_regime,
                    status,
                    created_at,
                ),
            )
            return int(cursor.lastrowid)

    def latest_walk_forward(
        self,
        *,
        instrument_uid: str,
        profile: str,
        risk_profile: str,
        strategy: str,
        accepted_only: bool = True,
    ) -> dict[str, Any] | None:
        query = """
            SELECT *
            FROM walk_forward_runs
            WHERE instrument_uid = ?
              AND profile = ?
              AND risk_profile = ?
              AND strategy = ?
        """
        params: list[Any] = [instrument_uid, profile, risk_profile, strategy]
        if accepted_only:
            query += " AND status = 'ACCEPTED'"
        query += " ORDER BY created_at DESC, id DESC LIMIT 1"
        with self._connect() as connection:
            row = connection.execute(query, params).fetchone()
        return dict(row) if row else None
