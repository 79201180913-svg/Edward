from __future__ import annotations

import logging
from statistics import mean
from typing import Iterable, Sequence

from edward.domain import TradingPathAnalysisV012, TradingPathValidationSummary
from edward.services.analysis_service import Candle
from edward.services.event_observation_v086 import EventObservationBuilderV086
from edward.services.trading_path_adaptive_discovery_service_v014 import TradingPathAdaptiveDiscoveryServiceV014
from edward.services.trading_path_adaptive_oos_service_v014 import TradingPathAdaptiveOOSServiceV014
from edward.services.trading_path_analysis_builder_v012 import TradingPathAnalysisBuilderV012
from edward.services.trading_path_candidate_pruning_service_v014 import (
    CandidatePruningConfigV014,
    TradingPathCandidatePruningServiceV014,
)
from edward.services.trading_path_candidate_service_v014 import TradingPathCandidateServiceV014
from edward.services.trading_path_decision_service_v012 import TradingPathDecisionServiceV012
from edward.services.trading_path_expected_value_service_v012 import TradingPathExpectedValueServiceV012
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSValidationServiceV012
from edward.services.trading_path_opportunity_builder_v012 import TradingPathOpportunityBuilderV012
from edward.services.trading_path_risk_service_v012 import TradingPathRiskServiceV012
from edward.services.trading_path_statistical_integrity_service_v014 import TradingPathStatisticalIntegrityServiceV014

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
    """Execute v0.8.14 nested path analysis without order execution.

    Temporal contract:
      TRAIN -> discovery, threshold selection and adaptive statistical control
      VALIDATION -> candidate selection
      OOS -> one final untouched evaluation used by risk/EV/opportunity/decision

    Fixed and adaptive candidates share the same downstream pipeline.
    """

    def analyze_paths(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles: Iterable[Candle],
        profile: str = "medium_term",
        risk_profile: str = "balanced",
    ) -> tuple[TradingPathAnalysisV012, ...]:
        ordered = tuple(sorted(candles, key=lambda item: item.timestamp))
        train, validation, oos = TradingPathStatisticalIntegrityServiceV014.partition_candles(ordered)
        split = TradingPathStatisticalIntegrityServiceV014.temporal_split(ordered)

        from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryServiceV086

        fixed_discovery = ConditionalDiscoveryServiceV086.run(train)
        fixed_candidates = TradingPathCandidateServiceV014.from_fixed(
            fixed_discovery, instrument_uid=instrument_uid, ticker=ticker
        )
        adaptive_discovery = TradingPathAdaptiveDiscoveryServiceV014.run(train)
        adaptive_candidates = TradingPathCandidateServiceV014.from_adaptive(
            adaptive_discovery, instrument_uid=instrument_uid, ticker=ticker
        )

        combined = TradingPathCandidateServiceV014.combine(
            fixed_candidates, adaptive_candidates, ticker=ticker
        )

        statistical_integrity = {}
        if adaptive_candidates:
            returns_by_candidate = {
                candidate: TradingPathAdaptiveOOSServiceV014.returns_in_range(
                    candidate, train, start=0, end=len(train)
                )
                for candidate in adaptive_candidates
            }
            horizons = {candidate: candidate.rule.horizon for candidate in adaptive_candidates}
            baseline_by_horizon = {
                horizon: mean(_baseline_returns(train, horizon)) if _baseline_returns(train, horizon) else 0.0
                for horizon in sorted({candidate.rule.horizon for candidate in adaptive_candidates})
            }
            statistical_integrity = TradingPathStatisticalIntegrityServiceV014.evaluate_candidate_returns(
                returns_by_candidate,
                baseline_return_pct_by_horizon=baseline_by_horizon,
                horizon_by_candidate=horizons,
            )

        candidates = TradingPathCandidatePruningServiceV014.prune(
            combined,
            config=CandidatePruningConfigV014(require_statistical_integrity=True),
            statistical_integrity=statistical_integrity,
        )

        observations = EventObservationBuilderV086.build(ordered)
        validation_size = split.validation_size
        validation_analysis = TradingPathAnalysisBuilderV012.build(
            candidates,
            ordered,
            validation_windows=1,
            validation_test_size=validation_size,
            validation_start=split.validation_start,
            validation_end=split.validation_end,
        )

        selected = tuple(
            analysis for analysis in validation_analysis
            if analysis.validation.promotion_status == "validated"
        )
        candidate_by_key = {
            (
                item.rule.instrument_uid,
                item.rule.ticker,
                item.rule.hypothesis,
                item.rule.regime,
                item.rule.volatility_bucket,
                item.rule.direction,
                item.rule.horizon,
            ): item
            for item in candidates
        }

        oos_size = split.oos_size
        if oos_size >= TradingPathOOSValidationServiceV012.DEFAULT_WINDOWS * TradingPathOOSValidationServiceV012.DEFAULT_TEST_SIZE:
            oos_windows = TradingPathOOSValidationServiceV012.DEFAULT_WINDOWS
            oos_test_size = TradingPathOOSValidationServiceV012.DEFAULT_TEST_SIZE
        else:
            oos_windows = 1
            oos_test_size = oos_size

        finalized: list[TradingPathAnalysisV012] = []
        for analysis in selected:
            key = (
                analysis.instrument_uid,
                analysis.ticker,
                analysis.hypothesis,
                analysis.regime,
                analysis.volatility_bucket,
                analysis.direction,
                analysis.horizon,
            )
            candidate = candidate_by_key.get(key)
            if candidate is None:
                continue

            oos_results = TradingPathOOSValidationServiceV012.validate(
                candidate,
                ordered,
                windows=oos_windows,
                test_size=oos_test_size,
                observations=observations,
                evaluation_start=split.oos_start,
                evaluation_end=split.oos_end,
            )
            expected_value = TradingPathExpectedValueServiceV012.calculate(
                candidate,
                ordered,
                windows=oos_windows,
                test_size=oos_test_size,
                observations=observations,
                evaluation_start=split.oos_start,
                evaluation_end=split.oos_end,
            )
            risk_result = TradingPathRiskServiceV012.evaluate(
                analysis,
                candles=ordered,
                profile=profile,
                oos_windows=oos_results,
            )
            with_opportunity = TradingPathOpportunityBuilderV012.build(
                analysis,
                expected_value=expected_value,
                risk_score=risk_result.risk.score,
                risk_gate=risk_result.path_eligible,
                oos_windows=oos_results,
            )
            result = TradingPathDecisionServiceV012.decide(with_opportunity)
            integrity = statistical_integrity.get(candidate)
            validation = with_opportunity.validation
            if integrity is not None:
                validation = TradingPathValidationSummary(
                    wf_persistence_pct=validation.wf_persistence_pct,
                    robustness_score=validation.robustness_score,
                    positive_oos_windows_pct=validation.positive_oos_windows_pct,
                    statistical_valid=integrity.statistically_valid,
                    overlap_valid=integrity.overlap_valid,
                    multiple_testing_valid=integrity.multiple_testing_valid,
                    promotion_status=validation.promotion_status,
                    effective_sample_size=integrity.effective_sample_size,
                    overlap_ratio_pct=integrity.overlap_ratio_pct,
                    standard_error_pct=integrity.standard_error_pct,
                    z_score=integrity.z_score,
                    p_value_one_sided=integrity.p_value_one_sided,
                    adjusted_p_value=integrity.adjusted_p_value,
                    hypotheses_tested=integrity.hypotheses_tested,
                )
            final = TradingPathAnalysisV012(
                instrument_uid=with_opportunity.instrument_uid,
                ticker=with_opportunity.ticker,
                strategy_family=with_opportunity.strategy_family,
                hypothesis=with_opportunity.hypothesis,
                regime=with_opportunity.regime,
                volatility_bucket=with_opportunity.volatility_bucket,
                direction=with_opportunity.direction,
                horizon=with_opportunity.horizon,
                evidence=with_opportunity.evidence,
                validation=validation,
                market_context=with_opportunity.market_context,
                opportunity=with_opportunity.opportunity,
                current_state=result.current_state,
                decision=result.decision,
                status=result.status,
                rank=with_opportunity.rank,
            )
            finalized.append(final)
            opportunity = final.opportunity
            logger.warning(
                "[V014 PATH DECISION] ticker=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d rank=%s validation=%s ev=%s risk=%s opportunity=%s confidence=%s decision=%s state=%s reason=%s",
                ticker, final.hypothesis, final.regime, final.volatility_bucket, final.direction, final.horizon,
                final.rank, _value(final.status), _field(opportunity, "expected_value_pct"), _field(opportunity, "risk_score"),
                _field(opportunity, "score"), _field(opportunity, "confidence"), _value(final.decision), _value(final.current_state),
                ",".join(result.reasons) or "READY",
            )

        logger.warning(
            "[V014 PATH RUNTIME] ticker=%s candles=%d train=%d validation=%d oos=%d discovered=%d selected=%d final=%d buy=%d wait=%d pass=%d",
            ticker, len(ordered), len(train), len(validation), len(oos), len(combined), len(selected), len(finalized),
            sum(_value(item.decision) == "buy" for item in finalized),
            sum(_value(item.decision) == "wait" for item in finalized),
            sum(_value(item.decision) == "pass" for item in finalized),
        )
        return tuple(finalized)


__all__ = ["AnalysisPathRuntimeServiceV012"]
