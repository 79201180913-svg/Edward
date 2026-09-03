from __future__ import annotations

import logging
from statistics import mean
from typing import Iterable, Sequence

from edward.domain import TradingPathAnalysisV012, TradingPathValidationSummary, TradingPathMarketContext, TradingPathCurrentState, TradingPathDecision, TradingPathAnalysisStatus
from edward.services.analysis_service import Candle
from edward.services.event_observation_v086 import EventObservationBuilderV086
from edward.services.trading_path_adaptive_discovery_service_v014 import TradingPathAdaptiveDiscoveryServiceV014
from edward.services.trading_path_adaptive_oos_service_v014 import TradingPathAdaptiveOOSServiceV014
from edward.services.trading_path_analysis_builder_v012 import TradingPathAnalysisBuilderV012
from edward.services.trading_path_candidate_pruning_service_v014 import CandidatePruningConfigV014, TradingPathCandidatePruningServiceV014
from edward.services.trading_path_candidate_service_v014 import TradingPathCandidateServiceV014
from edward.services.trading_path_expected_value_service_v012 import TradingPathExpectedValueServiceV012
from edward.services.trading_path_ev_evidence_service_v015 import TradingPathEVEvidenceServiceV015
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSValidationServiceV012
from edward.services.trading_path_opportunity_builder_v012 import TradingPathOpportunityBuilderV012
from edward.services.trading_path_risk_service_v012 import TradingPathRiskServiceV012
from edward.services.trading_path_statistical_integrity_service_v014 import TradingPathStatisticalIntegrityServiceV014
from edward.services.trading_path_walk_forward_service_v015 import TradingPathWalkForwardServiceV015
from edward.services.trading_path_market_context_service_v015 import TradingPathMarketContextServiceV015
from edward.services.trading_path_independent_oos_evidence_service_v015 import TradingPathIndependentOOSEvidenceServiceV015
from edward.services.trading_path_quality_gate_service_v015 import TradingPathQualityGateServiceV015

logger = logging.getLogger(__name__)


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _field(value: object, name: str) -> object:
    return getattr(value, name, None)


def _baseline_returns(candles: Sequence[Candle], horizon: int) -> tuple[float, ...]:
    values: list[float] = []
    for index in range(max(0, len(candles) - horizon)):
        start = float(candles[index].close)
        finish = float(candles[index + horizon].close)
        if start > 0.0 and finish > 0.0:
            values.append((finish / start - 1.0) * 100.0)
    return tuple(values)


class AnalysisPathRuntimeServiceV012:
    """Execute v0.8.15 nested path analysis without order execution."""

    @staticmethod
    def _candidate_key(candidate: object) -> tuple[object, ...]:
        rule = candidate.rule
        return (
            rule.instrument_uid, rule.ticker, rule.hypothesis,
            rule.regime, rule.volatility_bucket, rule.direction, rule.horizon,
        )

    @staticmethod
    def _analysis_key(analysis: TradingPathAnalysisV012) -> tuple[object, ...]:
        return (
            analysis.instrument_uid, analysis.ticker, analysis.hypothesis,
            analysis.regime, analysis.volatility_bucket, analysis.direction, analysis.horizon,
        )

    @classmethod
    def _discover_train_candidates(cls, train: Sequence[Candle], *, instrument_uid: str, ticker: str) -> tuple[object, ...]:
        from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryServiceV086
        fixed_discovery = ConditionalDiscoveryServiceV086.run(train)
        fixed_candidates = TradingPathCandidateServiceV014.from_fixed(fixed_discovery, instrument_uid=instrument_uid, ticker=ticker)
        adaptive_discovery = TradingPathAdaptiveDiscoveryServiceV014.run(train)
        adaptive_candidates = TradingPathCandidateServiceV014.from_adaptive(adaptive_discovery, instrument_uid=instrument_uid, ticker=ticker)
        combined = TradingPathCandidateServiceV014.combine(fixed_candidates, adaptive_candidates, ticker=ticker)
        statistical_integrity = {}
        if adaptive_candidates:
            returns_by_candidate = {candidate: TradingPathAdaptiveOOSServiceV014.returns_in_range(candidate, train, start=0, end=len(train)) for candidate in adaptive_candidates}
            observation_indices_by_candidate = {candidate: TradingPathAdaptiveOOSServiceV014.matching_indices(candidate, train) for candidate in adaptive_candidates}
            horizons = {candidate: candidate.rule.horizon for candidate in adaptive_candidates}
            unique_horizons = sorted({candidate.rule.horizon for candidate in adaptive_candidates})
            baseline_by_horizon = {horizon: mean(_baseline_returns(train, horizon)) if _baseline_returns(train, horizon) else 0.0 for horizon in unique_horizons}
            statistical_integrity = TradingPathStatisticalIntegrityServiceV014.evaluate_candidate_returns(returns_by_candidate, baseline_return_pct_by_horizon=baseline_by_horizon, horizon_by_candidate=horizons, observation_indices_by_candidate=observation_indices_by_candidate)
        return TradingPathCandidatePruningServiceV014.prune(combined, config=CandidatePruningConfigV014(require_statistical_integrity=True), statistical_integrity=statistical_integrity)

    def analyze_paths(self, *, instrument_uid: str, ticker: str, candles: Iterable[Candle], profile: str = "medium_term", risk_profile: str = "balanced", benchmark_candles: Iterable[Candle] | None = None, benchmark_id: str | None = None) -> tuple[TradingPathAnalysisV012, ...]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        benchmark_ordered = tuple(sorted(benchmark_candles, key=lambda item: item.timestamp)) if benchmark_candles is not None else None
        train, validation_candles, oos = TradingPathStatisticalIntegrityServiceV014.partition_candles(ordered)
        split = TradingPathStatisticalIntegrityServiceV014.temporal_split(ordered)
        nested = TradingPathWalkForwardServiceV015.nested_validate(ordered, discover=lambda fold_train: self._discover_train_candidates(fold_train, instrument_uid=instrument_uid, ticker=ticker), windows=TradingPathWalkForwardServiceV015.DEFAULT_WINDOWS, train_size=TradingPathWalkForwardServiceV015.DEFAULT_TRAIN_SIZE, validation_size=TradingPathWalkForwardServiceV015.DEFAULT_VALIDATION_SIZE)
        nested_by_key = {self._candidate_key(candidate): summary for candidate, summary in nested.candidate_summaries}
        nested_complete = len(nested.folds) == TradingPathWalkForwardServiceV015.DEFAULT_WINDOWS
        candidates = self._discover_train_candidates(train, instrument_uid=instrument_uid, ticker=ticker)
        statistical_integrity = {}
        adaptive_candidates = tuple(candidate for candidate in candidates if candidate.rule.hypothesis.upper().startswith("ADAPTIVE_RULE:"))
        if adaptive_candidates:
            returns_by_candidate = {candidate: TradingPathAdaptiveOOSServiceV014.returns_in_range(candidate, train, start=0, end=len(train)) for candidate in adaptive_candidates}
            observation_indices_by_candidate = {candidate: TradingPathAdaptiveOOSServiceV014.matching_indices(candidate, train) for candidate in adaptive_candidates}
            horizons = {candidate: candidate.rule.horizon for candidate in adaptive_candidates}
            unique_horizons = sorted({candidate.rule.horizon for candidate in adaptive_candidates})
            baseline_by_horizon = {horizon: mean(_baseline_returns(train, horizon)) if _baseline_returns(train, horizon) else 0.0 for horizon in unique_horizons}
            statistical_integrity = TradingPathStatisticalIntegrityServiceV014.evaluate_candidate_returns(returns_by_candidate, baseline_return_pct_by_horizon=baseline_by_horizon, horizon_by_candidate=horizons, observation_indices_by_candidate=observation_indices_by_candidate)
        observations = EventObservationBuilderV086.build(ordered)
        validation_analysis = TradingPathAnalysisBuilderV012.build(candidates, ordered, validation_windows=1, validation_test_size=split.validation_size, validation_start=split.validation_start, validation_end=split.validation_end)
        selected = tuple(analysis for analysis in validation_analysis if analysis.validation.promotion_status == "validated" and (not nested_complete or nested_by_key.get(self._analysis_key(analysis), None) is not None and nested_by_key[self._analysis_key(analysis)].passed))
        candidate_by_key = {self._candidate_key(item): item for item in candidates}
        oos_size = split.oos_size
        if oos_size >= TradingPathOOSValidationServiceV012.DEFAULT_WINDOWS * TradingPathOOSValidationServiceV012.DEFAULT_TEST_SIZE:
            oos_windows, oos_test_size = TradingPathOOSValidationServiceV012.DEFAULT_WINDOWS, TradingPathOOSValidationServiceV012.DEFAULT_TEST_SIZE
        else:
            oos_windows, oos_test_size = 1, oos_size
        finalized: list[TradingPathAnalysisV012] = []
        for analysis in selected:
            key = self._analysis_key(analysis)
            candidate = candidate_by_key.get(key)
            if candidate is None:
                continue
            oos_results = TradingPathOOSValidationServiceV012.validate(candidate, ordered, windows=oos_windows, test_size=oos_test_size, observations=observations, evaluation_start=split.oos_start, evaluation_end=split.oos_end)
            independent_oos_evidence = TradingPathIndependentOOSEvidenceServiceV015.build(candidate_key=key, oos_windows=oos_results, validation_start=split.validation_start, validation_end=split.validation_end, oos_start=split.oos_start, oos_end=split.oos_end)
            expected_value = TradingPathExpectedValueServiceV012.calculate(candidate, ordered, windows=oos_windows, test_size=oos_test_size, observations=observations, evaluation_start=split.oos_start, evaluation_end=split.oos_end)
            ev_evidence = TradingPathEVEvidenceServiceV015.build(tuple(window_return for window in oos_results for window_return in window.returns_pct))
            risk_result = TradingPathRiskServiceV012.evaluate(analysis, candles=ordered, profile=profile, oos_windows=oos_results)
            with_opportunity = TradingPathOpportunityBuilderV012.build(analysis, expected_value=expected_value, risk_score=risk_result.risk.score, risk_gate=risk_result.path_eligible, oos_windows=oos_results)
            final_validation = with_opportunity.validation
            integrity = statistical_integrity.get(key) if key in statistical_integrity else next((value for item, value in statistical_integrity.items() if self._candidate_key(item) == key), None)
            wf_summary = nested_by_key.get(key)
            if integrity is not None or wf_summary is not None:
                final_validation = TradingPathValidationSummary(wf_persistence_pct=(wf_summary.persistence_pct if wf_summary is not None else final_validation.wf_persistence_pct), robustness_score=final_validation.robustness_score, positive_oos_windows_pct=final_validation.positive_oos_windows_pct, statistical_valid=(integrity.statistically_valid if integrity is not None else final_validation.statistical_valid), overlap_valid=(integrity.overlap_valid if integrity is not None else final_validation.overlap_valid), multiple_testing_valid=(integrity.multiple_testing_valid if integrity is not None else final_validation.multiple_testing_valid), promotion_status=final_validation.promotion_status, effective_sample_size=(integrity.effective_sample_size if integrity is not None else final_validation.effective_sample_size), overlap_ratio_pct=(integrity.overlap_ratio_pct if integrity is not None else final_validation.overlap_ratio_pct), standard_error_pct=(integrity.standard_error_pct if integrity is not None else final_validation.standard_error_pct), z_score=(integrity.z_score if integrity is not None else final_validation.z_score), p_value_one_sided=(integrity.p_value_one_sided if integrity is not None else final_validation.p_value_one_sided), adjusted_p_value=(integrity.adjusted_p_value if integrity is not None else final_validation.adjusted_p_value), hypotheses_tested=(integrity.hypotheses_tested if integrity is not None else final_validation.hypotheses_tested))
            market_context = TradingPathMarketContextServiceV015.build_from_oos(candidate=candidate, instrument_candles=ordered, benchmark_candles=benchmark_ordered, oos_windows=oos_results, benchmark_id=benchmark_id)
            legacy_market_context = with_opportunity.market_context
            canonical_market_context = TradingPathMarketContext(benchmark_id=market_context.benchmark_id, baseline_rank=_field(legacy_market_context, "baseline_rank"), context_rank=_field(legacy_market_context, "context_rank"), rank_delta=_field(legacy_market_context, "rank_delta"), baseline_score=_field(legacy_market_context, "baseline_score"), context_adjusted_score=_field(legacy_market_context, "context_adjusted_score"), score_delta=_field(legacy_market_context, "score_delta"), regime_compatibility=_field(legacy_market_context, "regime_compatibility"), relative_strength_component=_field(legacy_market_context, "relative_strength_component"), volatility_component=_field(legacy_market_context, "volatility_component"), instrument_return_pct=market_context.instrument_return_pct, instrument_baseline_return_pct=market_context.instrument_baseline_return_pct, regime_baseline_return_pct=market_context.regime_baseline_return_pct, market_return_pct=market_context.market_return_pct, instrument_excess_pct=market_context.instrument_excess_pct, regime_excess_pct=market_context.regime_excess_pct, market_excess_pct=market_context.market_excess_pct, relative_strength_pct=market_context.relative_strength_pct, context_status=market_context.context_status, context_version=market_context.version)

            # V815-05: current state is a structural pre-gate state. It does not
            # inspect opportunity score/confidence, so the legacy weighted
            # decision service cannot silently override the explicit hard gate.
            pre_gate_current_state = (
                TradingPathCurrentState.ENTRY_READY
                if risk_result.path_eligible is True
                else TradingPathCurrentState.INVALID
            )
            quality_gate = TradingPathQualityGateServiceV015.evaluate(
                validation=final_validation,
                wf_summary=wf_summary,
                independent_oos_evidence=independent_oos_evidence,
                market_context=canonical_market_context,
                risk_gate=risk_result.path_eligible,
                current_state=pre_gate_current_state,
            )
            if quality_gate.passed:
                final_current_state = TradingPathCurrentState.ENTRY_READY
                final_decision = TradingPathDecision.BUY
                final_status = TradingPathAnalysisStatus.PROMOTABLE
            else:
                final_current_state = TradingPathCurrentState.INVALID
                final_decision = TradingPathDecision.PASS
                final_status = TradingPathAnalysisStatus.REJECTED

            final = TradingPathAnalysisV012(instrument_uid=with_opportunity.instrument_uid, ticker=with_opportunity.ticker, strategy_family=with_opportunity.strategy_family, hypothesis=with_opportunity.hypothesis, regime=with_opportunity.regime, volatility_bucket=with_opportunity.volatility_bucket, direction=with_opportunity.direction, horizon=with_opportunity.horizon, evidence=with_opportunity.evidence, validation=final_validation, market_context=canonical_market_context, opportunity=with_opportunity.opportunity, current_state=final_current_state, decision=final_decision, status=final_status, rank=with_opportunity.rank, independent_oos_evidence=independent_oos_evidence, quality_gate=quality_gate, ev_evidence=ev_evidence)
            finalized.append(final)
            opportunity = final.opportunity
            logger.warning("[V015 PATH DECISION] ticker=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d rank=%s validation=%s ev=%s ev_status=%s ev_ci_low=%s ev_reliability=%s ev_confidence=%s risk=%s opportunity=%s confidence=%s decision=%s state=%s reason=%s wf_persistence=%s market_context=%s oos_evidence=%s quality_gate=%s quality_reasons=%s", ticker, final.hypothesis, final.regime, final.volatility_bucket, final.direction, final.horizon, final.rank, _value(final.status), _field(opportunity, "expected_value_pct"), ev_evidence.status, ev_evidence.ev_ci_low_pct, ev_evidence.edge_reliability_pct, ev_evidence.confidence_score, _field(opportunity, "risk_score"), _field(opportunity, "score"), _field(opportunity, "confidence"), _value(final.decision), _value(final.current_state), ",".join(quality_gate.reasons) or "READY", _field(final.validation, "wf_persistence_pct"), final.market_context.context_status, independent_oos_evidence.status, quality_gate.passed, ",".join(quality_gate.reasons) or "READY")
        logger.warning("[V015 PATH RUNTIME] ticker=%s candles=%d train=%d validation=%d oos=%d discovered=%d selected=%d final=%d buy=%d wait=%d pass=%d nested_folds=%d nested_candidates=%d", ticker, len(ordered), len(train), len(validation_candles), len(oos), len(candidates), len(selected), len(finalized), sum(_value(item.decision) == "buy" for item in finalized), sum(_value(item.decision) == "wait" for item in finalized), sum(_value(item.decision) == "pass" for item in finalized), len(nested.folds), len(nested.candidate_summaries))
        return tuple(finalized)


__all__ = ["AnalysisPathRuntimeServiceV012"]
