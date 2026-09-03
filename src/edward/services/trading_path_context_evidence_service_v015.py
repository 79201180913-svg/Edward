from __future__ import annotations

from typing import Iterable, Any

from edward.domain import TradingPathContextV015
from edward.services.multifactor_analysis_service_v081 import MultiFactorAnalysisServiceV081, MultiFactorResult


CONTEXT_EVIDENCE_VERSION = "0.8.15"


class TradingPathContextEvidenceServiceV015:
    """Consume preserved v0.8.15 context through the existing factor layer.

    This service is deliberately an evidence adapter: it does not discover,
    validate, rank, or decide trading paths. It only maps the existing context
    envelope into the already-established v0.8.1 multifactor contract.
    """

    @staticmethod
    def analyze(
        *,
        context: TradingPathContextV015,
        candles: Iterable[Any] = (),
    ) -> MultiFactorResult:
        return MultiFactorAnalysisServiceV081.analyze(
            fundamentals=context.fundamentals,
            order_book=context.order_book,
            trades=context.trades,
            candles=tuple(candles),
            current_signal=context.current_signal,
            historical_signals=context.historical_signals,
            event=context.events,
            historical_gaps_pct=context.historical_gaps_pct,
            historical_event_vol_pct=context.historical_event_vol_pct,
            dividend_data=context.dividends,
            insider_transactions=context.insider,
            session_name=context.session_name,
            session_execution_allowed=context.session_execution_allowed,
            risk_data=context.risk_metadata,
            current_weight_pct=context.current_weight_pct,
            marginal_risk_pct=context.marginal_risk_pct,
            diversification_benefit_pct=context.diversification_benefit_pct,
            expected_return_impact_pct=context.expected_return_impact_pct,
            max_position_weight_pct=context.max_position_weight_pct,
            current_price=context.current_price,
        )


__all__ = ["CONTEXT_EVIDENCE_VERSION", "TradingPathContextEvidenceServiceV015"]
