from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

from edward.services.analysis_service import AnalysisResult, Candle, StrategyResult
from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryResult, ConditionalDiscoveryServiceV086
from edward.services.evidence_audit_service_v086 import EvidenceAuditServiceV086, EvidenceAuditV086, WFAwareEvidenceAuditV086
from edward.services.quality_gate_diagnostics_v0822 import QualityGateDiagnostics, QualityGateDiagnosticsServiceV0822
from edward.services.regime_engine_v08 import RegimeEngine
from edward.services.research_backtest_service_v08 import BacktestCostModel, ResearchBacktestService
from edward.services.research_discovery_service_v085 import ResearchDiscoveryResult, ResearchDiscoveryServiceV085
from edward.services.research_evidence_report_v086 import ResearchEvidenceReportServiceV086, ResearchEvidenceRowV086
from edward.services.research_evidence_summary_v087 import ResearchEvidenceSummaryServiceV087, ResearchEvidenceSummaryV087
from edward.services.robust_walk_forward_service_v08 import RobustWalkForwardResult, RobustWalkForwardService
from edward.services.robustness_diagnostics_v083 import RobustnessDiagnosticsServiceV083

logger = logging.getLogger(__name__)
ANALYSIS_V08_VERSION = "0.8.7"
LEGACY_ANALYSIS_RESULT_VERSION = "0.8.0"

@dataclass(frozen=True, slots=True)
class AnalysisV08Diagnostics:
    regime_confidence: float
    regime: str
    robustness_by_strategy: dict[str, float]
    quality_gate_by_strategy: dict[str, QualityGateDiagnostics]
    research_discovery: ResearchDiscoveryResult | None = None
    conditional_discovery: ConditionalDiscoveryResult | None = None
    evidence_audit: tuple[EvidenceAuditV086, ...] = ()
    wf_evidence: tuple[WFAwareEvidenceAuditV086, ...] = ()
    research_evidence: tuple[ResearchEvidenceRowV086, ...] = ()
    research_summary: ResearchEvidenceSummaryV087 | None = None

class AnalysisServiceV08:
    STRATEGIES = ("Trend Following", "Momentum", "Breakout", "Mean Reversion")
    PROFILES = {
        "long_term": {"train": 360, "test": 90, "max_drawdown_pct": 30.0, "min_stability_pct": 60.0},
        "medium_term": {"train": 240, "test": 60, "max_drawdown_pct": 25.0, "min_stability_pct": 60.0},
        "speculative": {"train": 120, "test": 30, "max_drawdown_pct": 35.0, "min_stability_pct": 55.0},
    }
    def __init__(self, *, costs: BacktestCostModel | None = None) -> None:
        self.costs = costs or BacktestCostModel()
        self.last_diagnostics: AnalysisV08Diagnostics | None = None
        logger.warning("[V087 EXEC] INIT AnalysisServiceV08 file=%s version=%s legacy_result_version=%s strategies=%s profiles=%s discovery=%s conditional=%s", __file__, ANALYSIS_V08_VERSION, LEGACY_ANALYSIS_RESULT_VERSION, self.STRATEGIES, self.PROFILES, ResearchDiscoveryServiceV085.HYPOTHESES, ConditionalDiscoveryServiceV086.HYPOTHESES)
    @staticmethod
    def _grid(strategy: str, profile: str) -> list[dict[str, Any]]:
        if strategy == "Trend Following": return [{"fast": fast, "slow": slow} for fast, slow in ((10, 30), (20, 50), (30, 90))]
        if strategy == "Momentum":
            values = (20, 40, 80) if profile == "long_term" else (10, 20, 40); return [{"lookback": value} for value in values]
        if strategy == "Breakout":
            values = (10, 20, 40) if profile == "speculative" else (20, 40, 80); return [{"lookback": value} for value in values]
        return [{"lookback": value, "deviation": deviation} for value in (10, 20, 40) for deviation in (1.5, 2.0, 3.0)]
    @staticmethod
    def _signal_factory(strategy: str, parameters: dict[str, Any]):
        return lambda candles, index: ResearchBacktestService.simple_signal(strategy, candles, parameters, index)
    def _robust(self, candles: list[Candle], strategy: str, profile: str) -> RobustWalkForwardResult:
        cfg = self.PROFILES[profile]
        logger.warning("[V083 EXEC] ENTER robust strategy=%s profile=%s candles=%d train=%d test=%d grid=%d", strategy, profile, len(candles), cfg["train"], cfg["test"], len(self._grid(strategy, profile)))
        result = RobustWalkForwardService.run(candles=candles, strategy=strategy, parameter_grid=self._grid(strategy, profile), signal_factory=self._signal_factory, train_size=cfg["train"], test_size=cfg["test"], costs=self.costs, max_drawdown_pct=cfg["max_drawdown_pct"])
        diagnostics = RobustnessDiagnosticsServiceV083.evaluate(result)
        logger.warning("[V083 ROBUSTNESS BREAKDOWN] strategy=%s return_score=%.2f return_contribution=%.2f risk_score=%.2f risk_contribution=%.2f sharpe_score=%.2f sharpe_contribution=%.2f stability_score=%.2f stability_contribution=%.2f performance_score=%.2f performance_contribution=%.2f total=%.2f", strategy, diagnostics.return_consistency_score, diagnostics.return_contribution, diagnostics.risk_consistency_score, diagnostics.risk_contribution, diagnostics.sharpe_consistency_score, diagnostics.sharpe_contribution, diagnostics.parameter_stability_score, diagnostics.parameter_stability_contribution, diagnostics.performance_consistency_score, diagnostics.performance_consistency_contribution, diagnostics.robustness_total)
        logger.warning("[V083 ROBUSTNESS ACTIVITY] strategy=%s windows=%d active=%d inactive=%d active_pct=%.2f positive_active=%d positive_active_pct=%.2f positive_all_pct=%.2f", strategy, diagnostics.total_windows, diagnostics.active_windows, diagnostics.inactive_windows, diagnostics.active_pct, diagnostics.positive_active_windows, diagnostics.positive_active_pct, diagnostics.positive_all_pct)
        logger.warning("[V083 EXEC] EXIT robust strategy=%s windows=%d robustness=%.2f mean_oos_return=%.4f mean_oos_dd=%.4f mean_oos_sharpe=%.4f", strategy, len(result.windows), result.robustness_score, result.mean_test_return_pct, result.mean_test_drawdown_pct, result.mean_test_sharpe)
        return result
    @staticmethod
    def _quality(result: RobustWalkForwardResult, profile: str) -> bool:
        diagnostics = QualityGateDiagnosticsServiceV0822.evaluate(result, profile)
        status = "PASS" if diagnostics.passed else "FAIL"
        logger.warning("[QUALITY GATE] strategy=%s profile=%s result=%s", result.strategy, profile, status)
        logger.warning("[V083 QG RESULT] strategy=%s profile=%s passed=%s failed_checks=%s reason=%s", result.strategy, profile, diagnostics.passed, diagnostics.failed_checks, diagnostics.failure_reason or "none")
        for check in diagnostics.checks: logger.warning("[V083 QG CHECK] strategy=%s check=%s actual=%.6f threshold=%.6f passed=%s", result.strategy, check.key, check.actual, check.threshold, check.passed)
        return diagnostics.passed
    @staticmethod
    def _legacy_strategy_result(result: RobustWalkForwardResult, profile: str) -> StrategyResult:
        quality = AnalysisServiceV08._quality(result, profile)
        return StrategyResult(strategy=result.strategy, parameters=dict(result.windows[-1].parameters) if result.windows else {}, return_pct=round(result.mean_test_return_pct, 8), max_drawdown_pct=round(result.mean_test_drawdown_pct, 8), sharpe=round(result.mean_test_sharpe, 8), trades=sum(item.test_trades for item in result.windows), stability=round(result.robustness_score, 8), quality_gate=quality, score=round(result.robustness_score, 8), train_score=round(sum(item.train_score for item in result.windows) / len(result.windows), 8) if result.windows else 0.0, test_score=round(result.mean_test_return_pct, 8), wf_windows=len(result.windows), positive_return_windows=result.positive_return_windows, risk_ok_windows=result.risk_ok_windows, positive_sharpe_windows=result.positive_sharpe_windows, return_consistency=round(result.return_consistency_pct, 8), risk_consistency=round(result.risk_consistency_pct, 8), sharpe_consistency=round(result.sharpe_consistency_pct, 8))
    def analyze(self, *, instrument_uid: str, ticker: str, candles: Iterable[Candle], profile: str = "medium_term", risk_profile: str = "balanced", horizon: str = "medium") -> AnalysisResult:
        if profile not in self.PROFILES: raise ValueError(f"Unsupported profile: {profile}")
        ordered = sorted(list(candles), key=lambda item: item.timestamp)
        minimum = self.PROFILES[profile]["train"] + self.PROFILES[profile]["test"]
        logger.warning("[V087 EXEC] ENTER AnalysisServiceV08 file=%s ticker=%s instrument_uid=%s profile=%s candles=%d minimum=%d", __file__, ticker, instrument_uid, profile, len(ordered), minimum)
        if len(ordered) < minimum: raise ValueError(f"Для v0.8-анализа требуется не менее {minimum} исторических свечей для профиля {profile}")
        regime_result = RegimeEngine.classify(ordered); logger.warning("[V085 EXEC] REGIME ticker=%s regime=%s confidence=%.4f", ticker, regime_result.regime, regime_result.confidence)
        discovery = ResearchDiscoveryServiceV085.run(ordered); conditional_discovery = ConditionalDiscoveryServiceV086.run(ordered); evidence_audit = EvidenceAuditServiceV086.audit(conditional_discovery)
        robust_results = [self._robust(ordered, strategy, profile) for strategy in self.STRATEGIES]
        wf_evidence: list[WFAwareEvidenceAuditV086] = []; wf_contexts: list[tuple[str, tuple[WFAwareEvidenceAuditV086, ...]]] = []
        for robust_result in robust_results:
            context_evidence = tuple(EvidenceAuditServiceV086.audit_wf(conditional_discovery, robust_result, ordered)); wf_evidence.extend(context_evidence); wf_contexts.append((robust_result.strategy, context_evidence))
        research_evidence = ResearchEvidenceReportServiceV086.build_from_wf_contexts(evidence_audit, wf_contexts); research_summary = ResearchEvidenceSummaryServiceV087.build(research_evidence)
        logger.warning("[V087 RESEARCH SUMMARY] ticker=%s cells=%d interesting=%d low_sample=%d no_positive_excess=%d low_wf_persistence=%d", ticker, research_summary.total_cells, research_summary.interesting, research_summary.low_sample, research_summary.no_positive_excess, research_summary.low_wf_persistence)
        for row in research_summary.top_magnitude: logger.warning("[V087 RESEARCH MAGNITUDE] ticker=%s strategy=%s rank=%d hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d N=%d excess=%.6f flag=%s", ticker, row.strategy_context, row.magnitude_rank, row.evidence.hypothesis, row.evidence.regime, row.evidence.volatility_bucket, row.evidence.direction, row.evidence.horizon, row.evidence.observations, row.evidence.excess_return_pct, row.research_flag)
        for row in research_summary.top_consistency: logger.warning("[V087 RESEARCH CONSISTENCY] ticker=%s strategy=%s rank=%d hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d N=%d win_rate=%.2f flag=%s", ticker, row.strategy_context, row.consistency_rank, row.evidence.hypothesis, row.evidence.regime, row.evidence.volatility_bucket, row.evidence.direction, row.evidence.horizon, row.evidence.observations, row.evidence.win_rate_pct, row.research_flag)
        for row in research_summary.top_stability: logger.warning("[V087 RESEARCH STABILITY] ticker=%s strategy=%s rank=%d hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d N=%d wf_persistence=%.2f flag=%s", ticker, row.strategy_context, row.stability_rank, row.evidence.hypothesis, row.evidence.regime, row.evidence.volatility_bucket, row.evidence.direction, row.evidence.horizon, row.evidence.observations, row.wf.wf_persistence_pct if row.wf else 0.0, row.research_flag)
        strategies = [self._legacy_strategy_result(item, profile) for item in robust_results]; passed = [item for item in strategies if item.quality_gate]; winner = max(passed, key=lambda item: item.score) if passed else None
        recommendation = winner.strategy if winner else None; confidence = "Low"
        if winner: confidence = "High" if winner.stability >= 80.0 else "Medium" if winner.stability >= 65.0 else "Low"
        self.last_diagnostics = AnalysisV08Diagnostics(regime_confidence=regime_result.confidence, regime=regime_result.regime, robustness_by_strategy={item.strategy: item.robustness_score for item in robust_results}, quality_gate_by_strategy={item.strategy: QualityGateDiagnosticsServiceV0822.evaluate(item, profile) for item in robust_results}, research_discovery=discovery, conditional_discovery=conditional_discovery, evidence_audit=evidence_audit, wf_evidence=tuple(wf_evidence), research_evidence=research_evidence, research_summary=research_summary)
        explanation = (f"Рекомендована {winner.strategy}: v0.8 robustness {winner.score:.1f}, OOS return {winner.return_pct:.2f}%, Sharpe {winner.sharpe:.2f}, режим {regime_result.regime}, regime confidence {regime_result.confidence:.0f}%." if winner else f"Ни одна стратегия не прошла v0.8 Quality Gate; режим {regime_result.regime}, regime confidence {regime_result.confidence:.0f}%. Исследовательские слои v0.8.5/v0.8.6/v0.8.7 дополнительно проверили структурные, условные и доказательные гипотезы без влияния на допуск к торговле.")
        return AnalysisResult(instrument_uid=instrument_uid, ticker=ticker, profile=profile, risk_profile=risk_profile, horizon=horizon, market_regime=regime_result.regime, recommendation=recommendation, confidence=confidence, score=winner.score if winner else 0.0, strategies=strategies, explanation=explanation, created_at=ordered[-1].timestamp.isoformat(), analysis_version=ANALYSIS_V08_VERSION)
