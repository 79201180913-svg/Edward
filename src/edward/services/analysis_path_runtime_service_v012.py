from __future__ import annotations

import logging
from typing import Iterable

from edward.domain import TradingPathAnalysisV012
from edward.services.analysis_service import Candle
from edward.services.trading_path_analysis_builder_v012 import TradingPathAnalysisBuilderV012
from edward.services.trading_path_decision_service_v012 import TradingPathDecisionServiceV012
from edward.services.trading_path_expected_value_service_v012 import TradingPathExpectedValueServiceV012
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSValidationServiceV012
from edward.services.trading_path_opportunity_builder_v012 import TradingPathOpportunityBuilderV012
from edward.services.trading_path_risk_service_v012 import TradingPathRiskServiceV012

logger = logging.getLogger(__name__)


def _value(value: object) -> object:
    return getattr(value, "value", value)


def _field(value: object, name: str) -> object:
    return getattr(value, name, None)


class AnalysisPathRuntimeServiceV012:
    """Execute the complete v0.8.12 path analysis without order execution."""

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
        from edward.services.conditional_discovery_service_v086 import ConditionalDiscoveryServiceV086
        from edward.services.trading_path_candidate_service_v088 import TradingPathCandidateServiceV088

        discovery = ConditionalDiscoveryServiceV086.run(ordered)
        candidates = TradingPathCandidateServiceV088.promote(discovery, instrument_uid=instrument_uid, ticker=ticker)
        analyses = TradingPathAnalysisBuilderV012.build(candidates, ordered)
        finalized: list[TradingPathAnalysisV012] = []

        for analysis in analyses:
            candidate = next(
                (
                    item for item in candidates
                    if item.rule.hypothesis == analysis.hypothesis
                    and item.rule.regime == analysis.regime
                    and item.rule.volatility_bucket == analysis.volatility_bucket
                    and item.rule.direction == analysis.direction
                    and item.rule.horizon == analysis.horizon
                ),
                None,
            )
            if candidate is None:
                continue
            oos_windows = TradingPathOOSValidationServiceV012.validate(candidate, ordered)
            expected_value = TradingPathExpectedValueServiceV012.calculate(candidate, ordered)
            risk_result = TradingPathRiskServiceV012.evaluate(
                analysis,
                candles=ordered,
                profile=profile,
                oos_windows=oos_windows,
            )
            with_opportunity = TradingPathOpportunityBuilderV012.build(
                analysis,
                expected_value=expected_value,
                risk_score=risk_result.risk.score,
                risk_gate=risk_result.path_eligible,
                oos_windows=oos_windows,
            )
            result = TradingPathDecisionServiceV012.decide(with_opportunity)
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
                validation=with_opportunity.validation,
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
                "[V012 PATH DECISION] ticker=%s hypothesis=%s regime=%s volatility=%s direction=%s horizon=%d rank=%s validation=%s ev=%s risk=%s opportunity=%s confidence=%s decision=%s state=%s reason=%s",
                ticker, final.hypothesis, final.regime, final.volatility_bucket, final.direction, final.horizon,
                final.rank, _value(final.status), _field(opportunity, "expected_value_pct"), _field(opportunity, "risk_score"),
                _field(opportunity, "score"), _field(opportunity, "confidence"), _value(final.decision), _value(final.current_state),
                ",".join(result.reasons) or "READY",
            )

        logger.warning(
            "[V012 PATH RUNTIME] ticker=%s candidates=%d analyses=%d buy=%d wait=%d pass=%d",
            ticker, len(candidates), len(finalized),
            sum(_value(item.decision) == "buy" for item in finalized),
            sum(_value(item.decision) == "wait" for item in finalized),
            sum(_value(item.decision) == "pass" for item in finalized),
        )
        return tuple(finalized)


__all__ = ["AnalysisPathRuntimeServiceV012"]
