from __future__ import annotations

from edward.services.fundamental_analysis_service_v082 import FundamentalAnalysisResult
from edward.services.multifactor_analysis_service_v081 import Evidence, FundamentalFactor


class FundamentalFactorAdapterV082:
    """Adapt the structured v0.8.2 fundamental result to the stable v0.8.1 factor contract."""

    @staticmethod
    def adapt(result: FundamentalAnalysisResult) -> FundamentalFactor:
        score = float(result.overall_score)
        direction = "POSITIVE" if score >= 60.0 else "NEGATIVE" if score < 40.0 else "NEUTRAL"
        evidence = Evidence(
            "fundamentals",
            direction,
            score,
            float(result.confidence),
            available=result.status != "UNAVAILABLE",
            reason=(result.reason_codes[0] if result.reason_codes else None),
        )
        return FundamentalFactor(
            quality_score=result.business_quality.score,
            growth_score=result.growth.score,
            valuation_score=result.valuation.score,
            balance_sheet_score=result.financial_health.score,
            cash_flow_score=result.cash_generation.score,
            shareholder_return_score=result.shareholder_return.score,
            momentum_score=result.fundamental_momentum.score,
            evidence=evidence,
        )


__all__ = ["FundamentalFactorAdapterV082"]
