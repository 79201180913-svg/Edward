from edward.services.analysis_service import AnalysisResult, AnalysisService
from edward.services.strategy_confidence_policy_v06 import StrategyConfidencePolicy


class StrategyConfidenceIntegration:
    """Apply the v0.6 strategy-confidence business rule without altering forecast confidence."""

    @staticmethod
    def resolve_analysis_confidence(*, quality_gate: bool, confidence: str | None) -> str:
        return StrategyConfidencePolicy.resolve(
            quality_gate=quality_gate,
            confidence=confidence,
        )

    @classmethod
    def normalize_result(cls, result: AnalysisResult, *, quality_gate: bool) -> AnalysisResult:
        confidence = cls.resolve_analysis_confidence(
            quality_gate=quality_gate,
            confidence=result.confidence,
        )
        return AnalysisResult(
            instrument_uid=result.instrument_uid,
            ticker=result.ticker,
            profile=result.profile,
            risk_profile=result.risk_profile,
            horizon=result.horizon,
            market_regime=result.market_regime,
            recommendation=result.recommendation,
            confidence=confidence,
            score=result.score,
            strategies=result.strategies,
            explanation=result.explanation,
            created_at=result.created_at,
            analysis_version=result.analysis_version,
        )


__all__ = ["StrategyConfidenceIntegration"]
