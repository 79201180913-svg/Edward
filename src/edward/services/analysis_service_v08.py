from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable

from edward.services.analysis_service import AnalysisResult, Candle, StrategyResult
from edward.services.quality_gate_diagnostics_v0822 import QualityGateDiagnostics, QualityGateDiagnosticsServiceV0822
from edward.services.regime_engine_v08 import RegimeEngine
from edward.services.regime_conditioned_evidence_v084 import RegimeConditionedEvidence, RegimeConditionedEvidenceServiceV084
from edward.services.generalization_diagnostics_v084 import GeneralizationDiagnosticsV084, GeneralizationDiagnosticsServiceV084
from edward.services.parameter_zone_v084 import ParameterZoneV084
from edward.services.parameter_zone_oos_diagnostics_v084 import ParameterZoneOOSDiagnosticsV084, ParameterZoneOOSDiagnosticsServiceV084
from edward.services.failure_attribution_v084 import FailureAttributionV084, FailureAttributionServiceV084
from edward.services.failure_attribution_summary_v084 import FailureAttributionSummaryV084, FailureAttributionSummaryServiceV084
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestService
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult
from edward.services.robust_walk_forward_service_v084 import RobustWalkForwardServiceV084
from edward.services.robustness_diagnostics_v083 import RobustnessDiagnosticsServiceV083
from edward.services.strategy_router_v084 import StrategyRouterV084
from edward.services.train_sample_diagnostics_v084 import TrainSampleDiagnosticsV084, TrainSampleDiagnosticsServiceV084

logger = logging.getLogger(__name__)
ANALYSIS_V08_VERSION = "0.8.0"
ANALYSIS_ENGINE_V084_VERSION = "0.8.4"

@dataclass(frozen=True, slots=True)
class AnalysisV08Diagnostics:
    regime_confidence: float
    regime: str
    robustness_by_strategy: dict[str, float]
    quality_gate_by_strategy: dict[str, QualityGateDiagnostics]
    router_compatibility_by_strategy: dict[str, float] = field(default_factory=dict)
    router_priority_by_strategy: dict[str, str] = field(default_factory=dict)
    router_ordered_strategies: tuple[str, ...] = ()
    regime_evidence_by_strategy: dict[str, RegimeConditionedEvidence] = field(default_factory=dict)
    generalization_by_strategy: dict[str, GeneralizationDiagnosticsV084] = field(default_factory=dict)
    parameter_zone_by_strategy: dict[str, tuple[ParameterZoneV084, ...]] = field(default_factory=dict)
    parameter_zone_oos_by_strategy: dict[str, ParameterZoneOOSDiagnosticsV084] = field(default_factory=dict)
    train_sample_by_strategy: dict[str, TrainSampleDiagnosticsV084] = field(default_factory=dict)
    failure_attribution_by_strategy: dict[str, FailureAttributionV084] = field(default_factory=dict)
    failure_attribution_summary: FailureAttributionSummaryV084 | None = None

class AnalysisServiceV08:
    STRATEGIES = ("Trend Following", "Momentum", "Breakout", "Mean Reversion")
    PROFILES = {
        "long_term": {"train": 360, "test": 90, "max_drawdown_pct": 30.0, "min_stability_pct": 60.0, "min_train_trades": 1},
        "medium_term": {"train": 240, "test": 60, "max_drawdown_pct": 25.0, "min_stability_pct": 60.0, "min_train_trades": 1},
        "speculative": {"train": 120, "test": 30, "max_drawdown_pct": 35.0, "min_stability_pct": 55.0, "min_train_trades": 1},
    }
    def __init__(self, *, costs: BacktestCostModel | None = None) -> None:
        self.costs = costs or BacktestCostModel()
        self.last_diagnostics: AnalysisV08Diagnostics | None = None
        logger.warning("[V084 EXEC] INIT AnalysisServiceV08 engine_version=%s contract_version=%s strategies=%s profiles=%s", ANALYSIS_ENGINE_V084_VERSION, ANALYSIS_V08_VERSION, self.STRATEGIES, self.PROFILES)
    @staticmethod
    def _grid(strategy: str, profile: str) -> list[dict[str, Any]]:
        if strategy == "Trend Following": return [{"fast": fast, "slow": slow} for fast, slow in ((10, 30), (20, 50), (30, 90))]
        if strategy == "Momentum": return [{"lookback": value} for value in ((20, 40, 80) if profile == "long_term" else (10, 20, 40))]
        if strategy == "Breakout": return [{"lookback": value} for value in ((10, 20, 40) if profile == "speculative" else (20, 40, 80))]
        return [{"lookback": value, "deviation": deviation} for value in (10, 20, 40) for deviation in (1.5, 2.0, 3.0)]
    @staticmethod
    def _signal_factory(strategy: str, parameters: dict[str, Any]):
        return lambda candles, index: ResearchBacktestService.simple_signal(strategy, candles, parameters, index)
    def _robust(self, candles: list[Candle], strategy: str, profile: str) -> RobustWalkForwardResult:
        cfg = self.PROFILES[profile]
        try:
            result = RobustWalkForwardServiceV084.run(candles=candles, strategy=strategy, parameter_grid=self._grid(strategy, profile), signal_factory=self._signal_factory, train_size=cfg["train"], test_size=cfg["test"], costs=self.costs, max_drawdown_pct=cfg["max_drawdown_pct"], min_train_trades=cfg["min_train_trades"])
        except ValueError as exc:
            logger.warning("[V084 WF INVALID STRATEGY] strategy=%s profile=%s reason=%s", strategy, profile, exc)
            return RobustWalkForwardServiceV084._empty(strategy)
        diagnostics = RobustnessDiagnosticsServiceV083.evaluate(result)
        logger.warning("[V084 ROBUSTNESS BREAKDOWN] strategy=%s total=%.2f return_score=%.2f risk_score=%.2f sharpe_score=%.2f stability_score=%.2f performance_score=%.2f", strategy, diagnostics.robustness_total, diagnostics.return_consistency_score, diagnostics.risk_consistency_score, diagnostics.sharpe_consistency_score, diagnostics.parameter_stability_score, diagnostics.performance_consistency_score)
        return result
    @staticmethod
    def _quality(result: RobustWalkForwardResult, profile: str) -> bool:
        diagnostics = QualityGateDiagnosticsServiceV0822.evaluate(result, profile)
        logger.warning("[V084 QG RESULT] strategy=%s profile=%s passed=%s failed_checks=%s reason=%s", result.strategy, profile, diagnostics.passed, diagnostics.failed_checks, diagnostics.failure_reason or "none")
        for check in diagnostics.checks:
            logger.warning("[V084 QG CHECK] strategy=%s check=%s actual=%.6f threshold=%.6f passed=%s", result.strategy, check.key, check.actual, check.threshold, check.passed)
        logger.warning("[QUALITY GATE] strategy=%s profile=%s result=%s", result.strategy, profile, "PASS" if diagnostics.passed else "FAIL")
        return diagnostics.passed
    @staticmethod
    def _legacy_strategy_result(result: RobustWalkForwardResult, profile: str) -> StrategyResult:
        quality = AnalysisServiceV08._quality(result, profile)
        return StrategyResult(strategy=result.strategy, parameters=dict(result.windows[-1].parameters) if result.windows else {}, return_pct=round(result.mean_test_return_pct, 8), max_drawdown_pct=round(result.mean_test_drawdown_pct, 8), sharpe=round(result.mean_test_sharpe, 8), trades=sum(item.test_trades for item in result.windows), stability=round(result.robustness_score, 8), quality_gate=quality, score=round(result.robustness_score, 8), train_score=round(sum(item.train_score for item in result.windows) / len(result.windows), 8) if result.windows else 0.0, test_score=round(result.mean_test_return_pct, 8), wf_windows=len(result.windows), positive_return_windows=result.positive_return_windows, risk_ok_windows=result.risk_ok_windows, positive_sharpe_windows=result.positive_sharpe_windows, return_consistency=round(result.return_consistency_pct, 8), risk_consistency=round(result.risk_consistency_pct, 8), sharpe_consistency=round(result.sharpe_consistency_pct, 8))
    def analyze(self, *, instrument_uid: str, ticker: str, candles: Iterable[Candle], profile: str = "medium_term", risk_profile: str = "balanced", horizon: str = "medium") -> AnalysisResult:
        if profile not in self.PROFILES: raise ValueError(f"Unsupported profile: {profile}")
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        minimum = self.PROFILES[profile]["train"] + self.PROFILES[profile]["test"]
        if len(ordered) < minimum: raise ValueError(f"Для v0.8-анализа требуется не менее {minimum} исторических свечей для профиля {profile}")
        regime_result = RegimeEngine.classify(ordered)
        router = StrategyRouterV084.route(regime_result, self.STRATEGIES, ticker=ticker)
        robust_results = [self._robust(ordered, strategy, profile) for strategy in self.STRATEGIES]
        strategies = [self._legacy_strategy_result(item, profile) for item in robust_results]
        passed = [item for item in strategies if item.quality_gate]
        compatibility = {item.strategy: next((d.compatibility for d in router.decisions if d.strategy == item.strategy), 0.0) for item in strategies}
        regime_evidence = {item.strategy: RegimeConditionedEvidenceServiceV084.evaluate(robust_results[index], ordered, regime_result.regime, regime_result.confidence, ticker=ticker) for index, item in enumerate(strategies)}
        generalization = {item.strategy: GeneralizationDiagnosticsServiceV084.evaluate(robust_results[index], regime_evidence.get(item.strategy), ticker=ticker) for index, item in enumerate(strategies)}
        parameter_zones = {item.strategy: tuple(getattr(robust_results[index], "parameter_zone_diagnostics", ())) for index, item in enumerate(strategies)}
        parameter_zone_oos = {item.strategy: ParameterZoneOOSDiagnosticsServiceV084.evaluate(strategy=item.strategy, windows=robust_results[index].windows, zones=parameter_zones[item.strategy]) for index, item in enumerate(strategies) if parameter_zones[item.strategy] and len(parameter_zones[item.strategy]) == len(robust_results[index].windows)}
        train_sample = {item.strategy: TrainSampleDiagnosticsServiceV084.evaluate(getattr(robust_results[index], "selected_train_trades", ())) for index, item in enumerate(strategies)}
        failure_attribution = {}
        for index, item in enumerate(strategies):
            qg = QualityGateDiagnosticsServiceV0822.evaluate(robust_results[index], profile)
            zone_oos = parameter_zone_oos.get(item.strategy)
            sample = train_sample[item.strategy]
            failure_attribution[item.strategy] = FailureAttributionServiceV084.evaluate(strategy=item.strategy, quality_gate_passed=qg.passed, quality_gate_failure_reason=qg.failure_reason if not qg.passed else None, quality_gate_failed_checks=qg.failed_checks, low_sample_pct=sample.low_sample_pct, oos_mean_return_pct=robust_results[index].mean_test_return_pct, oos_positive_pct=robust_results[index].return_consistency_pct, stable_zone_pct=(zone_oos.stable_windows / zone_oos.windows * 100.0) if zone_oos and zone_oos.windows else 0.0, viable_windows=len(robust_results[index].windows))
        failure_summary = FailureAttributionSummaryServiceV084.evaluate(failure_attribution.values())
        self.last_diagnostics = AnalysisV08Diagnostics(regime_confidence=regime_result.confidence, regime=regime_result.regime, robustness_by_strategy={item.strategy: item.robustness_score for item in robust_results}, quality_gate_by_strategy={item.strategy: QualityGateDiagnosticsServiceV0822.evaluate(item, profile) for item in robust_results}, router_compatibility_by_strategy=compatibility, router_priority_by_strategy={item.strategy: item.priority for item in router.decisions}, router_ordered_strategies=router.ordered_strategies, regime_evidence_by_strategy=regime_evidence, generalization_by_strategy=generalization, parameter_zone_by_strategy=parameter_zones, parameter_zone_oos_by_strategy=parameter_zone_oos, train_sample_by_strategy=train_sample, failure_attribution_by_strategy=failure_attribution, failure_attribution_summary=failure_summary)
        logger.warning("[V084 FAILURE ATTRIBUTION SUMMARY] ticker=%s total=%d passed=%d failed=%d counts=%s dominant=%s", ticker, failure_summary.total_strategies, failure_summary.passed_strategies, failure_summary.failed_strategies, failure_summary.primary_reason_counts, failure_summary.dominant_failure_reason)
        winner = max(passed, key=lambda item: (item.score, compatibility.get(item.strategy, 0.0))) if passed else None
        recommendation = winner.strategy if winner else None
        confidence = "Low" if not winner else "High" if winner.stability >= 80.0 else "Medium" if winner.stability >= 65.0 else "Low"
        explanation = f"Рекомендована {winner.strategy}: v0.8.4 robustness {winner.score:.1f}, OOS return {winner.return_pct:.2f}%, Sharpe {winner.sharpe:.2f}, режим {regime_result.regime}, regime confidence {regime_result.confidence:.0f}%." if winner else f"Ни одна стратегия не прошла v0.8.4 Quality Gate; режим {regime_result.regime}, regime confidence {regime_result.confidence:.0f}%."
        return AnalysisResult(instrument_uid=instrument_uid, ticker=ticker, profile=profile, risk_profile=risk_profile, horizon=horizon, market_regime=regime_result.regime, recommendation=recommendation, confidence=confidence, score=winner.score if winner else 0.0, strategies=strategies, explanation=explanation, created_at=ordered[-1].timestamp.isoformat(), analysis_version=ANALYSIS_V08_VERSION)

__all__ = ["ANALYSIS_V08_VERSION", "ANALYSIS_ENGINE_V084_VERSION", "AnalysisV08Diagnostics", "AnalysisServiceV08"]
