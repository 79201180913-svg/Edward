from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edward.services.analysis_service import ANALYSIS_VERSION, Candle, StrategyResult


class StrategyOptimizationCache:
    """Persistent cache for Walk Forward strategy optimization results."""

    def __init__(self, storage_path: str | Path):
        self.storage_path = Path(storage_path).expanduser().resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.db_path = self.storage_path / "edward.db"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def fingerprint(
        *,
        instrument_uid: str,
        profile: str,
        risk_profile: str,
        strategy: str,
        candles: list[Candle],
    ) -> str:
        payload = {
            "instrument_uid": instrument_uid,
            "profile": profile,
            "risk_profile": risk_profile,
            "strategy": strategy,
            "analysis_version": ANALYSIS_VERSION,
            "candles": [
                [
                    item.timestamp.isoformat(),
                    float(item.open),
                    float(item.high),
                    float(item.low),
                    float(item.close),
                    float(item.volume),
                ]
                for item in candles
            ],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _result_from_row(row: sqlite3.Row) -> StrategyResult:
        metrics = json.loads(row["metrics_json"] or "{}")
        return StrategyResult(
            strategy=str(row["strategy"]),
            parameters=json.loads(row["parameters_json"] or "{}"),
            return_pct=float(metrics.get("return_pct", 0.0)),
            max_drawdown_pct=float(metrics.get("max_drawdown_pct", 0.0)),
            sharpe=float(metrics.get("sharpe", 0.0)),
            trades=int(metrics.get("trades", 0)),
            stability=float(metrics.get("stability", 0.0)),
            quality_gate=str(row["status"]) == "ACCEPTED",
            score=float(metrics.get("score", 0.0)),
            train_score=float(metrics.get("train_score", 0.0)),
            test_score=float(metrics.get("test_score", 0.0)),
            wf_windows=int(metrics.get("wf_windows", 0)),
            positive_return_windows=int(metrics.get("positive_return_windows", 0)),
            risk_ok_windows=int(metrics.get("risk_ok_windows", 0)),
            positive_sharpe_windows=int(metrics.get("positive_sharpe_windows", 0)),
            return_consistency=float(metrics.get("return_consistency", 0.0)),
            risk_consistency=float(metrics.get("risk_consistency", 0.0)),
            sharpe_consistency=float(metrics.get("sharpe_consistency", 0.0)),
        )

    def get(
        self,
        *,
        instrument_uid: str,
        profile: str,
        risk_profile: str,
        strategy: str,
        fingerprint: str,
    ) -> tuple[int, StrategyResult] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM walk_forward_runs
                WHERE instrument_uid = ?
                  AND profile = ?
                  AND risk_profile = ?
                  AND strategy = ?
                  AND strategy_version = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (instrument_uid, profile, risk_profile, strategy, ANALYSIS_VERSION),
            ).fetchone()
        if row is None:
            return None
        try:
            metrics = json.loads(row["metrics_json"] or "{}")
        except (TypeError, ValueError):
            return None
        if metrics.get("cache_fingerprint") != fingerprint:
            return None
        return int(row["id"]), self._result_from_row(row)

    def save(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        profile: str,
        risk_profile: str,
        strategy: str,
        result: StrategyResult,
        candles: list[Candle],
        market_regime: str,
    ) -> int:
        fingerprint = self.fingerprint(
            instrument_uid=instrument_uid,
            profile=profile,
            risk_profile=risk_profile,
            strategy=strategy,
            candles=candles,
        )
        created_at = datetime.now(timezone.utc).isoformat()
        metrics: dict[str, Any] = {
            "return_pct": result.return_pct,
            "max_drawdown_pct": result.max_drawdown_pct,
            "sharpe": result.sharpe,
            "trades": result.trades,
            "stability": result.stability,
            "score": result.score,
            "train_score": result.train_score,
            "test_score": result.test_score,
            "wf_windows": result.wf_windows,
            "positive_return_windows": result.positive_return_windows,
            "risk_ok_windows": result.risk_ok_windows,
            "positive_sharpe_windows": result.positive_sharpe_windows,
            "return_consistency": result.return_consistency,
            "risk_consistency": result.risk_consistency,
            "sharpe_consistency": result.sharpe_consistency,
            "cache_fingerprint": fingerprint,
        }
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
                    ANALYSIS_VERSION,
                    candles[0].timestamp.isoformat() if candles else None,
                    candles[-1].timestamp.isoformat() if candles else None,
                    profile,
                    profile,
                    profile,
                    json.dumps(result.parameters, ensure_ascii=False, sort_keys=True),
                    json.dumps(metrics, ensure_ascii=False, sort_keys=True),
                    market_regime,
                    "ACCEPTED" if result.quality_gate else "REJECTED",
                    created_at,
                ),
            )
            return int(cursor.lastrowid)

    def clear_current(self, *, instrument_uid: str, profile: str, risk_profile: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM walk_forward_runs WHERE instrument_uid = ? AND profile = ? AND risk_profile = ? AND strategy_version = ?",
                (instrument_uid, profile, risk_profile, ANALYSIS_VERSION),
            )
            return int(cursor.rowcount)

    def clear_all(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM walk_forward_runs WHERE strategy_version = ?",
                (ANALYSIS_VERSION,),
            )
            return int(cursor.rowcount)

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM walk_forward_runs WHERE strategy_version = ?",
                (ANALYSIS_VERSION,),
            ).fetchone()
        return int(row["count"] if row else 0)
