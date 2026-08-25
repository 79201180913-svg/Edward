from __future__ import annotations

import json
from typing import Any

from edward.storage.sqlite_store import SQLiteStore


class AnalysisSnapshotRepository:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def save(self, result: Any, walk_forward_run_id: int | None = None) -> int:
        confidence = {"High": 1.0, "Medium": 0.7, "Low": 0.4}.get(result.confidence, 0.0)
        with self.store._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO analysis_snapshots (
                    instrument_uid, ticker, profile, risk_profile, horizon,
                    strategy, walk_forward_run_id, signal, confidence,
                    entry_price, stop_loss, take_profit, risk_reward,
                    market_regime, explanation_json, valid_until,
                    invalidation_conditions_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.instrument_uid,
                    result.ticker,
                    result.profile,
                    result.risk_profile,
                    result.horizon,
                    result.recommendation,
                    walk_forward_run_id,
                    "RECOMMENDATION" if result.recommendation else "NO_RECOMMENDATION",
                    confidence,
                    None,
                    None,
                    None,
                    None,
                    result.market_regime,
                    json.dumps({"text": result.explanation, "analysis_version": result.analysis_version}, ensure_ascii=False),
                    None,
                    json.dumps([], ensure_ascii=False),
                    result.created_at,
                ),
            )
            return int(cursor.lastrowid)

    def latest(self, instrument_uid: str, profile: str, risk_profile: str) -> dict[str, Any] | None:
        with self.store._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM analysis_snapshots
                WHERE instrument_uid = ? AND profile = ? AND risk_profile = ?
                ORDER BY created_at DESC, id DESC LIMIT 1
                """,
                (instrument_uid, profile, risk_profile),
            ).fetchone()
        return dict(row) if row else None
