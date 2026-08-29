from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from edward.services.analysis_service import AnalysisResult, Candle
from edward.services.analysis_service_v08 import AnalysisServiceV08, AnalysisV08Diagnostics
from edward.services.regime_engine_v08 import RegimeEngine
from edward.services.strategy_optimization_cache import StrategyOptimizationCache


class CachedAnalysisServiceV08(AnalysisServiceV08):
    """v0.8 analysis facade with the existing persisted WF cache contract."""

    def __init__(self, store, *, force_recompute: bool = False):
        super().__init__()
        self.store = store
        self.force_recompute = force_recompute
        self.last_cache_hits = 0
        self.last_cache_misses = 0
        self.last_cache_run_ids: dict[str, int] = {}

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        profile: str = "medium_term",
        risk_profile: str = "balanced",
        horizon: str = "medium",
    ) -> AnalysisResult:
        if profile not in self.PROFILES:
            raise ValueError(f"Unsupported profile: {profile}")
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        minimum = self.PROFILES[profile]["train"] + self.PROFILES[profile]["test"]
        if len(ordered) < minimum:
            raise ValueError(f"Для v0.8-анализа требуется не менее {minimum} исторических свечей для профиля {profile}")

        cache = StrategyOptimizationCache(self.store.data_dir if self.store is not None else "data")
        regime_result = RegimeEngine.classify(ordered)
        strategies = []
        self.last_cache_hits = 0
        self.last_cache_misses = 0
        self.last_cache_run_ids = {}

        for strategy in self.STRATEGIES:
            fingerprint = cache.fingerprint(
                instrument_uid=instrument_uid,
                profile=profile,
                risk_profile=risk_profile,
                strategy=strategy,
                candles=ordered,
            )
            cached = None if self.force_recompute else cache.get(
                instrument_uid=instrument_uid,
                profile=profile,
                risk_profile=risk_profile,
                strategy=strategy,
                fingerprint=fingerprint,
            )
            if cached is not None:
                run_id, strategy_result = cached
                self.last_cache_hits += 1
                self.last_cache_run_ids[strategy] = run_id
                strategies.append(strategy_result)
                continue

            self.last_cache_misses += 1
            robust_result = self._robust(ordered, strategy, profile)
            strategy_result = self._legacy_strategy_result(robust_result, profile)
            run_id = cache.save(
                instrument_uid=instrument_uid,
                ticker=ticker,
                profile=profile,
                risk_profile=risk_profile,
                strategy=strategy,
                result=strategy_result,
                candles=ordered,
                market_regime=regime_result.regime,
            )
            self.last_cache_run_ids[strategy] = run_id
            strategies.append(strategy_result)

        self.force_recompute = False
        passed = [item for item in strategies if item.quality_gate]
        winner = max(passed, key=lambda item: item.score) if passed else None
        recommendation = winner.strategy if winner else None
        confidence = "Low"
        if winner:
            confidence = "High" if winner.stability >= 80.0 else "Medium" if winner.stability >= 65.0 else "Low"
        self.last_diagnostics = AnalysisV08Diagnostics(
            regime_confidence=regime_result.confidence,
            regime=regime_result.regime,
            robustness_by_strategy={item.strategy: item.stability for item in strategies},
        )

        explanation = (
            f"Рекомендована {winner.strategy}: v0.8 robustness {winner.score:.1f}, "
            f"OOS return {winner.return_pct:.2f}%, Sharpe {winner.sharpe:.2f}, "
            f"режим {regime_result.regime}, regime confidence {regime_result.confidence:.0f}%."
            if winner else
            f"Ни одна стратегия не прошла v0.8 Quality Gate; режим {regime_result.regime}, "
            f"regime confidence {regime_result.confidence:.0f}%."
        )
        return AnalysisResult(
            instrument_uid=instrument_uid,
            ticker=ticker,
            profile=profile,
            risk_profile=risk_profile,
            horizon=horizon,
            market_regime=regime_result.regime,
            recommendation=recommendation,
            confidence=confidence,
            score=winner.score if winner else 0.0,
            strategies=strategies,
            explanation=explanation,
            created_at=ordered[-1].timestamp.isoformat() if ordered else datetime.now(timezone.utc).isoformat(),
            analysis_version="0.8.0",
        )

    def cache_info(self) -> dict[str, int]:
        return {
            "hits": self.last_cache_hits,
            "misses": self.last_cache_misses,
            "total": self.last_cache_hits + self.last_cache_misses,
        }


__all__ = ["CachedAnalysisServiceV08"]
