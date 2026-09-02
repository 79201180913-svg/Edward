from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, ClassVar, Iterable

from edward.domain import TradingPathAnalysisV012
from edward.services.analysis_service import StrategyResult
from edward.services.analysis_path_runtime_service_v012 import AnalysisPathRuntimeServiceV012


OPPORTUNITY_CANONICAL_ADAPTER_VERSION = "0.8.15"


@dataclass(frozen=True, slots=True)
class CanonicalOpportunityAnalysisV015:
    """Opportunity-facing view over canonical v0.8.14 path analyses.

    The adapter owns no analysis logic. It delegates calculation to the
    canonical v0.8.14 path runtime and exposes the minimum shape consumed by
    Opportunity Search.
    """

    analyses: tuple[TradingPathAnalysisV012, ...]

    _cache: ClassVar[dict[tuple[str, str, str, str], "CanonicalOpportunityAnalysisV015"]] = {}

    @classmethod
    def analyze(
        cls,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Any],
        profile: str = "medium_term",
        instrument: Any | None = None,
        force_recompute: bool = False,
    ) -> "CanonicalOpportunityAnalysisV015":
        del instrument
        candle_tuple = tuple(candles)
        cache_key = cls._cache_key(instrument_uid, ticker, profile, candle_tuple)
        if not force_recompute:
            cached = cls._cache.get(cache_key)
            if cached is not None:
                return cached

        analyses = AnalysisPathRuntimeServiceV012().analyze_paths(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=candle_tuple,
            profile=profile,
        )
        result = cls.from_analyses(analyses)
        cls._cache[cache_key] = result
        return result

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()

    @staticmethod
    def _cache_key(
        instrument_uid: str,
        ticker: str,
        profile: str,
        candles: tuple[Any, ...],
    ) -> tuple[str, str, str, str]:
        digest = sha256()
        for candle in candles:
            digest.update(repr(candle).encode("utf-8", errors="replace"))
            digest.update(b"\n")
        return (
            str(instrument_uid),
            str(ticker),
            str(profile),
            digest.hexdigest(),
        )

    @property
    def pipeline_result(self) -> TradingPathAnalysisV012 | None:
        """Compatibility projection for the existing Opportunity engine."""
        return self.best_analysis

    @property
    def market_regime(self) -> str | None:
        analysis = self.best_analysis
        return analysis.regime if analysis is not None else None

    @property
    def confidence(self) -> float | None:
        analysis = self.best_analysis
        return analysis.opportunity.confidence if analysis is not None else None

    @property
    def opportunity(self) -> Any | None:
        analysis = self.best_analysis
        return analysis.opportunity if analysis is not None else None

    @property
    def best_analysis(self) -> TradingPathAnalysisV012 | None:
        if not self.analyses:
            return None
        return min(
            self.analyses,
            key=lambda item: (
                item.rank is None,
                item.rank if item.rank is not None else 10**9,
                -(float(item.opportunity.score) if item.opportunity.score is not None else 0.0),
            ),
        )

    @property
    def strategies(self) -> tuple[StrategyResult, ...]:
        return tuple(self._strategy_result(item) for item in self.analyses)

    @property
    def canonical_results(self) -> tuple[TradingPathAnalysisV012, ...]:
        return self.analyses

    @staticmethod
    def _strategy_result(analysis: TradingPathAnalysisV012) -> StrategyResult:
        evidence = analysis.evidence
        return_pct = float(getattr(evidence, "mean_forward_return_pct", 0.0) or 0.0)
        max_drawdown = float(getattr(evidence, "max_drawdown_pct", 0.0) or 0.0)
        score = float(analysis.opportunity.score or 0.0)
        stability = float(analysis.validation.robustness_score or 0.0)
        quality_gate = bool(
            analysis.validation.promotion_status in {"validated", "promotable", "promoted"}
            and analysis.validation.statistical_valid is True
            and analysis.validation.overlap_valid is not False
            and analysis.validation.multiple_testing_valid is not False
        )
        return StrategyResult(
            strategy=analysis.strategy_family,
            parameters={
                "hypothesis": analysis.hypothesis,
                "regime": analysis.regime,
                "volatility_bucket": analysis.volatility_bucket,
                "direction": analysis.direction,
                "horizon": analysis.horizon,
                "source": "adaptive" if analysis.hypothesis.startswith("ADAPTIVE_RULE:") else "fixed",
            },
            return_pct=return_pct,
            max_drawdown_pct=max_drawdown,
            sharpe=0.0,
            trades=int(getattr(evidence, "observations", 0) or 0),
            stability=stability,
            quality_gate=quality_gate,
            score=score,
            train_score=return_pct,
            test_score=float(analysis.validation.positive_oos_windows_pct or 0.0),
            wf_windows=1,
            positive_return_windows=1 if (analysis.validation.positive_oos_windows_pct or 0.0) > 0.0 else 0,
            risk_ok_windows=1 if analysis.opportunity.risk_gate else 0,
            positive_sharpe_windows=0,
            return_consistency=stability,
            risk_consistency=float(analysis.opportunity.risk_score or 0.0),
            sharpe_consistency=0.0,
        )

    @classmethod
    def from_analyses(cls, analyses: Iterable[TradingPathAnalysisV012]) -> "CanonicalOpportunityAnalysisV015":
        return cls(tuple(analyses))


__all__ = ["OPPORTUNITY_CANONICAL_ADAPTER_VERSION", "CanonicalOpportunityAnalysisV015"]
