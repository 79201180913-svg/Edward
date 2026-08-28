from __future__ import annotations

from dataclasses import dataclass, replace
from logging import getLogger
from typing import Any, Mapping, Sequence

from edward.services.analysis_pipeline_service_v08 import AnalysisPipelineServiceV08, AnalysisPipelineV08Result
from edward.services.fundamental_analysis_service_v082 import FundamentalAnalysisServiceV082
from edward.services.multifactor_analysis_service_v081 import Evidence, MultiFactorAnalysisServiceV081, MultiFactorResult
from edward.services.multifactor_normalization_v081 import normalize
from edward.services.multifactor_overlay_service_v081 import MultiFactorOverlayResult, MultiFactorOverlayServiceV081
from edward.services import multifactor_risk_calibration_v081 as _multifactor_risk_calibration_v081  # noqa: F401

ANALYSIS_PIPELINE_V081_VERSION = "0.8.1"
logger = getLogger(__name__)


def _normalize_margin_rate(value: Any) -> float | None:
    if value is None:
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= normalized <= 1.0:
        return normalized * 100.0
    return normalized


def _normalize_risk_data(risk_data: Any) -> Any:
    if risk_data is None:
        return None
    if not isinstance(risk_data, Mapping):
        return risk_data
    normalized = dict(risk_data)
    raw_dlong = risk_data.get("dlong")
    raw_dshort = risk_data.get("dshort")
    raw_dlong_client = risk_data.get("dlong_client")
    raw_dshort_client = risk_data.get("dshort_client")
    for key in ("dlong", "dlong_client"):
        source = risk_data.get(key)
        normalized[key] = _normalize_margin_rate(source)
    for key in ("dshort", "dshort_client"):
        source = risk_data.get(key)
        normalized[key] = _normalize_margin_rate(source)
    logger.info(
        "[V081 RISK NORMALIZE] raw_dlong=%r raw_dshort=%r raw_dlong_client=%r raw_dshort_client=%r "
        "normalized_dlong=%r normalized_dshort=%r normalized_dlong_client=%r normalized_dshort_client=%r short_enabled=%r",
        raw_dlong,
        raw_dshort,
        raw_dlong_client,
        raw_dshort_client,
        normalized.get("dlong"),
        normalized.get("dshort"),
        normalized.get("dlong_client"),
        normalized.get("dshort_client"),
        normalized.get("short_enabled", normalized.get("short_enabled_flag")),
    )
    return normalized


def _fundamental_factor_from_v082(result) -> Any:
    groups = {
        "quality_score": result.business_quality.score,
        "growth_score": result.growth.score,
        "valuation_score": result.valuation.score,
        "balance_sheet_score": result.financial_health.score,
        "cash_flow_score": result.cash_generation.score,
        "shareholder_return_score": result.shareholder_return.score,
        "momentum_score": result.fundamental_momentum.score,
    }
    score = float(result.overall_score)
    direction = "POSITIVE" if score >= 60.0 else "NEGATIVE" if score < 40.0 else "NEUTRAL"
    available = result.status != "UNAVAILABLE"
    reason = result.reason_codes[0] if result.reason_codes else None
    evidence = Evidence(
        "fundamentals",
        direction if available else "UNAVAILABLE",
        score if available else 0.0,
        float(result.confidence) if available else 0.0,
        available=available,
        reason=reason,
    )
    from edward.services.multifactor_analysis_service_v081 import FundamentalFactor
    return FundamentalFactor(**groups, evidence=evidence)


def _replace_fundamental_factor(multifactor: MultiFactorResult, fundamental_result) -> MultiFactorResult:
    fundamental = _fundamental_factor_from_v082(fundamental_result)
    evidence = [
        fundamental.evidence,
        multifactor.microstructure.evidence,
        multifactor.volume_pressure.evidence,
        multifactor.signals.evidence,
        multifactor.event_risk.evidence,
        multifactor.dividends.evidence,
        multifactor.insider.evidence,
        multifactor.session.evidence,
        multifactor.instrument_risk.evidence,
        multifactor.portfolio.evidence,
    ]
    score, reliability, conflict = MultiFactorAnalysisServiceV081.aggregate(evidence)
    return replace(
        multifactor,
        fundamentals=fundamental,
        aggregate_evidence_score=score,
        aggregate_reliability_score=reliability,
        conflict_penalty=conflict,
    )


@dataclass(frozen=True, slots=True)
class AnalysisPipelineV081Result:
    base: AnalysisPipelineV08Result
    multifactor: MultiFactorResult
    overlay: MultiFactorOverlayResult
    version: str = ANALYSIS_PIPELINE_V081_VERSION

    @property
    def analysis(self):
        return self.base.analysis

    @property
    def opportunity(self):
        return self.base.opportunity

    @property
    def expected_value(self):
        return self.base.expected_value

    @property
    def portfolio_impact(self):
        return self.base.portfolio_impact

    @property
    def forecast_quality_score(self):
        return self.base.forecast_quality_score

    @property
    def regime_confidence(self):
        return self.base.regime_confidence

    @property
    def evidence_strategy(self):
        return self.base.evidence_strategy

    @property
    def portfolio_context_available(self):
        return self.base.portfolio_context_available

    @property
    def confidence(self):
        base_confidence = self.base.confidence
        if base_confidence is None:
            return None
        level = "High" if self.overlay.adjusted_confidence >= 75.0 else "Medium" if self.overlay.adjusted_confidence >= 55.0 else "Low"
        return replace(
            base_confidence,
            overall_confidence=self.overlay.adjusted_confidence,
            level=level,
        )


class AnalysisPipelineServiceV081:
    """v0.8.1 additive facade over the stable v0.8 analysis pipeline."""

    def __init__(self, *, base_pipeline: AnalysisPipelineServiceV08 | None = None) -> None:
        self.base_pipeline = base_pipeline or AnalysisPipelineServiceV08()

    def analyze(
        self,
        *,
        instrument_uid: str,
        ticker: str,
        candles,
        profile: str = "medium_term",
        risk_profile: str = "balanced",
        horizon: str = "medium",
        portfolio_weights: Mapping[str, float] | None = None,
        portfolio_returns: Mapping[str, Sequence[float]] | None = None,
        candidate_weight: float = 0.0,
        concentration_penalty_pct: float = 0.0,
        fundamentals: Any = None,
        order_book: Any = None,
        trades: Sequence[Any] | None = None,
        current_signal: Any = None,
        historical_signals: Sequence[Any] | None = None,
        event: Any = None,
        historical_gaps_pct: Sequence[float] | None = None,
        historical_event_vol_pct: Sequence[float] | None = None,
        dividend_data: Any = None,
        insider_transactions: Sequence[Any] | None = None,
        session_name: str | None = None,
        session_execution_allowed: bool = True,
        risk_data: Any = None,
        instrument_risk_metadata: Any = None,
        current_weight_pct: float = 0.0,
        marginal_risk_pct: float = 0.0,
        diversification_benefit_pct: float = 0.0,
        expected_return_impact_pct: float = 0.0,
        max_position_weight_pct: float | None = None,
        current_price: float | None = None,
    ) -> AnalysisPipelineV081Result:
        base = self.base_pipeline.analyze(
            instrument_uid=instrument_uid,
            ticker=ticker,
            candles=candles,
            profile=profile,
            risk_profile=risk_profile,
            horizon=horizon,
            portfolio_weights=portfolio_weights,
            portfolio_returns=portfolio_returns,
            candidate_weight=candidate_weight,
            concentration_penalty_pct=concentration_penalty_pct,
        )
        effective_risk_data = instrument_risk_metadata if instrument_risk_metadata is not None else risk_data
        normalized_risk_data = _normalize_risk_data(effective_risk_data)
        logger.info(
            "[V081 RISK BEFORE FACTOR] instrument_uid=%s source=%s risk_data=%r",
            instrument_uid,
            "instrument_metadata" if instrument_risk_metadata is not None else "risk_rates",
            normalized_risk_data,
        )
        # v0.8.2 is now the single source of truth for the fundamental factor.
        # Pass None into the legacy calculator so it cannot score the same data twice.
        multifactor = MultiFactorAnalysisServiceV081.analyze(
            fundamentals=None,
            order_book=order_book,
            trades=trades,
            candles=candles,
            current_signal=current_signal,
            historical_signals=historical_signals,
            event=event,
            historical_gaps_pct=historical_gaps_pct,
            historical_event_vol_pct=historical_event_vol_pct,
            dividend_data=dividend_data,
            insider_transactions=insider_transactions,
            session_name=session_name,
            session_execution_allowed=session_execution_allowed,
            risk_data=normalized_risk_data,
            current_weight_pct=current_weight_pct,
            marginal_risk_pct=marginal_risk_pct,
            diversification_benefit_pct=diversification_benefit_pct,
            expected_return_impact_pct=expected_return_impact_pct,
            max_position_weight_pct=max_position_weight_pct,
            current_price=current_price,
        )
        fundamental_result = FundamentalAnalysisServiceV082.analyze(fundamentals, profile=profile)
        logger.info(
            "[V082 FUNDAMENTAL PIPELINE] instrument_uid=%s profile=%s score=%.2f confidence=%.2f coverage=%.2f status=%s "
            "business_quality=%.2f growth=%.2f cash_generation=%.2f financial_health=%.2f valuation=%.2f shareholder_return=%.2f momentum=%.2f",
            instrument_uid,
            fundamental_result.strategy_profile,
            fundamental_result.overall_score,
            fundamental_result.confidence,
            fundamental_result.coverage,
            fundamental_result.status,
            fundamental_result.business_quality.score,
            fundamental_result.growth.score,
            fundamental_result.cash_generation.score,
            fundamental_result.financial_health.score,
            fundamental_result.valuation.score,
            fundamental_result.shareholder_return.score,
            fundamental_result.fundamental_momentum.score,
        )
        multifactor = _replace_fundamental_factor(multifactor, fundamental_result)
        logger.info(
            "[V081 FUNDAMENTAL FACTOR] instrument_uid=%s score=%.2f reliability=%.2f available=%r reason=%r "
            "aggregate_evidence=%.2f conflict=%.2f",
            instrument_uid,
            multifactor.fundamentals.evidence.strength,
            multifactor.fundamentals.evidence.reliability,
            multifactor.fundamentals.evidence.available,
            multifactor.fundamentals.evidence.reason,
            multifactor.aggregate_evidence_score,
            multifactor.conflict_penalty,
        )
        logger.info(
            "[V081 RISK FACTOR] instrument_uid=%s dlong=%r dshort=%r short_enabled=%r "
            "capital_efficiency=%.2f risk_score=%.2f evidence_available=%r reason=%r",
            instrument_uid,
            multifactor.instrument_risk.long_margin_rate_pct,
            multifactor.instrument_risk.short_margin_rate_pct,
            multifactor.instrument_risk.short_enabled,
            multifactor.instrument_risk.capital_efficiency_score,
            multifactor.instrument_risk.risk_score,
            multifactor.instrument_risk.evidence.available,
            multifactor.instrument_risk.evidence.reason,
        )
        multifactor = normalize(
            multifactor,
            portfolio_context_available=bool(
                portfolio_weights or portfolio_returns or candidate_weight > 0 or current_weight_pct > 0 or marginal_risk_pct != 0 or diversification_benefit_pct != 0
            ),
            session_available=session_name is not None,
        )
        adjusted, overlay = MultiFactorOverlayServiceV081.apply(base, multifactor)
        logger.info(
            "[V081 OVERLAY] instrument_uid=%s base_opportunity=%.2f adjusted_opportunity=%.2f "
            "base_confidence=%s adjusted_confidence=%.2f evidence=%.2f reliability=%.2f conflicts=%.2f",
            instrument_uid,
            float(base.opportunity.score),
            float(adjusted.opportunity.score),
            base.confidence.overall_confidence if base.confidence is not None else None,
            overlay.adjusted_confidence,
            overlay.evidence_score,
            overlay.evidence_reliability,
            overlay.conflict_penalty,
        )
        return AnalysisPipelineV081Result(adjusted, multifactor, overlay)


__all__ = ["ANALYSIS_PIPELINE_V081_VERSION", "AnalysisPipelineV081Result", "AnalysisPipelineServiceV081"]
