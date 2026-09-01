from __future__ import annotations

import logging

from edward.domain import TradingPathAnalysisV012, TradingPathOpportunity
from edward.services.expected_value_engine_v08 import ExpectedValueResult
from edward.services.trading_path_oos_validation_service_v012 import TradingPathOOSWindowV012

logger = logging.getLogger(__name__)


class TradingPathOpportunityBuilderV012:
    """Build a path-level opportunity from path-specific evidence only.

    Opportunity is deliberately decision-independent. No StrategyResult and no
    legacy OpportunityEngine are required for the canonical path calculation.
    """

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @classmethod
    def _ev_score(cls, expected_value_pct: float | None) -> float | None:
        if expected_value_pct is None:
            return None
        # Keep the same practical scale used by the existing v0.8 EV scorer.
        return cls._clamp(50.0 + float(expected_value_pct) * 8.0)

    @classmethod
    def _validation_score(
        cls,
        analysis: TradingPathAnalysisV012,
        oos_windows: tuple[TradingPathOOSWindowV012, ...],
    ) -> float | None:
        validation = analysis.validation
        components: list[float] = []
        if validation.wf_persistence_pct is not None:
            components.append(cls._clamp(validation.wf_persistence_pct))
        if validation.robustness_score is not None:
            components.append(cls._clamp(validation.robustness_score))
        if validation.positive_oos_windows_pct is not None:
            components.append(cls._clamp(validation.positive_oos_windows_pct))
        if oos_windows:
            components.append(
                cls._clamp(
                    sum(window.excess_return_pct > 0.0 for window in oos_windows)
                    / len(oos_windows)
                    * 100.0
                )
            )
        if not components:
            return None
        return sum(components) / len(components)

    @classmethod
    def _confidence_score(cls, expected_value: ExpectedValueResult | None) -> float | None:
        if expected_value is None or expected_value.edge_reliability_pct is None:
            return None
        return cls._clamp(expected_value.edge_reliability_pct)

    @classmethod
    def score_path(
        cls,
        analysis: TradingPathAnalysisV012,
        *,
        expected_value: ExpectedValueResult | None,
        risk_score: float | None,
        risk_gate: bool | None,
        oos_windows: tuple[TradingPathOOSWindowV012, ...] = (),
    ) -> TradingPathOpportunity:
        """Calculate opportunity score from path-level components.

        Weights:
        - EV: 35%
        - risk: 25%
        - OOS validation: 25%
        - EV reliability: 15%

        Missing components are not replaced with invented neutral values; the
        score stays unavailable until all four path-level components exist.
        """
        ev_value = expected_value.expected_value_pct if expected_value is not None else None
        ev_score = cls._ev_score(ev_value)
        validation_score = cls._validation_score(analysis, oos_windows)
        confidence = cls._confidence_score(expected_value)

        if ev_score is None or risk_score is None or validation_score is None or confidence is None:
            score = None
        else:
            score = round(
                ev_score * 0.35
                + cls._clamp(risk_score) * 0.25
                + validation_score * 0.25
                + confidence * 0.15,
                2,
            )

        logger.warning(
            "[V012 PATH OPPORTUNITY] ticker=%s hypothesis=%s ev_score=%s risk_score=%s validation_score=%s confidence=%s score=%s risk_gate=%s",
            analysis.ticker,
            analysis.hypothesis,
            ev_score,
            risk_score,
            validation_score,
            confidence,
            score,
            risk_gate,
        )
        return TradingPathOpportunity(
            score=score,
            confidence=confidence,
            expected_value_pct=ev_value,
            risk_score=risk_score,
            risk_gate=risk_gate,
        )

    @classmethod
    def from_components(
        cls,
        analysis: TradingPathAnalysisV012,
        *,
        expected_value_pct: float | None,
        risk_score: float | None,
        risk_gate: bool | None,
        score: float | None = None,
        confidence: float | None = None,
    ) -> TradingPathAnalysisV012:
        """Compatibility constructor for callers that already have components."""
        opportunity = TradingPathOpportunity(
            score=score,
            confidence=confidence,
            expected_value_pct=expected_value_pct,
            risk_score=risk_score,
            risk_gate=risk_gate,
        )
        return cls._with_opportunity(analysis, opportunity)

    @staticmethod
    def _with_opportunity(
        analysis: TradingPathAnalysisV012,
        opportunity: TradingPathOpportunity,
    ) -> TradingPathAnalysisV012:
        return TradingPathAnalysisV012(
            instrument_uid=analysis.instrument_uid,
            ticker=analysis.ticker,
            strategy_family=analysis.strategy_family,
            hypothesis=analysis.hypothesis,
            regime=analysis.regime,
            volatility_bucket=analysis.volatility_bucket,
            direction=analysis.direction,
            horizon=analysis.horizon,
            evidence=analysis.evidence,
            validation=analysis.validation,
            market_context=analysis.market_context,
            opportunity=opportunity,
            current_state=analysis.current_state,
            decision=analysis.decision,
            status=analysis.status,
            rank=analysis.rank,
        )

    @classmethod
    def build(
        cls,
        analysis: TradingPathAnalysisV012,
        *,
        expected_value: ExpectedValueResult | None,
        risk_score: float | None,
        risk_gate: bool | None,
        oos_windows: tuple[TradingPathOOSWindowV012, ...] = (),
    ) -> TradingPathAnalysisV012:
        """Attach the canonical path-level opportunity to an analysis snapshot."""
        return cls._with_opportunity(
            analysis,
            cls.score_path(
                analysis,
                expected_value=expected_value,
                risk_score=risk_score,
                risk_gate=risk_gate,
                oos_windows=oos_windows,
            ),
        )


__all__ = ["TradingPathOpportunityBuilderV012"]
