from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Iterable

from edward.services.analysis_service import ANALYSIS_VERSION, AnalysisResult, AnalysisService, Candle, StrategyResult
from edward.services.strategy_optimization_cache import StrategyOptimizationCache


class CachedAnalysisService(AnalysisService):
    """AnalysisService variant that reuses persisted Walk Forward results."""

    def __init__(self, store, *, force_recompute: bool = False):
        super().__init__(store)
        self.force_recompute = force_recompute
        self.last_cache_hits = 0
        self.last_cache_misses = 0
        self.last_cache_run_ids: dict[str, int] = {}

    @classmethod
    def _build_result(
        cls,
        *,
        instrument_uid: str,
        ticker: str,
        profile: str,
        risk_profile: str,
        horizon: str,
        regime: str,
        results: list[StrategyResult],
    ) -> AnalysisResult:
        passed = [item for item in results if item.quality_gate]
        winner = max(passed, key=lambda item: item.score) if passed else None
        confidence = "Low"
        if winner:
            confidence = "High" if winner.stability >= 80 and winner.score >= 75 else "Medium" if winner.stability >= 65 and winner.score >= 60 else "Low"
        explanation = (
            f"Рекомендована {winner.strategy}: Score {winner.score:.1f}, "
            f"Walk Forward stability {winner.stability:.0f}%, режим {regime}."
            if winner else "Ни одна стратегия не прошла Quality Gate; рекомендация не сформирована."
        )
        return AnalysisResult(
            instrument_uid,
            ticker,
            profile,
            risk_profile,
            horizon,
            regime,
            winner.strategy if winner else None,
            confidence,
            winner.score if winner else 0.0,
            results,
            explanation,
            datetime.now(timezone.utc).isoformat(),
            ANALYSIS_VERSION,
        )

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
        if len(ordered) < 150:
            raise ValueError("Для beta-анализа требуется не менее 150 исторических свечей")

        cache = StrategyOptimizationCache(self.store.data_dir if self.store is not None else "data")
        regime = self.market_regime(ordered)
        results: list[StrategyResult] = []
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
                results.append(strategy_result)
                continue

            self.last_cache_misses += 1
            strategy_result = self.walk_forward(ordered, strategy, profile)
            run_id = cache.save(
                instrument_uid=instrument_uid,
                ticker=ticker,
                profile=profile,
                risk_profile=risk_profile,
                strategy=strategy,
                result=strategy_result,
                candles=ordered,
                market_regime=regime,
            )
            self.last_cache_run_ids[strategy] = run_id
            results.append(strategy_result)

        self.force_recompute = False
        return self._build_result(
            instrument_uid=instrument_uid,
            ticker=ticker,
            profile=profile,
            risk_profile=risk_profile,
            horizon=horizon,
            regime=regime,
            results=results,
        )

    def save(self, result: AnalysisResult) -> int | None:
        return self.last_cache_run_ids.get(result.recommendation or "")

    def cache_info(self) -> dict[str, int]:
        return {"hits": self.last_cache_hits, "misses": self.last_cache_misses, "total": self.last_cache_hits + self.last_cache_misses}
