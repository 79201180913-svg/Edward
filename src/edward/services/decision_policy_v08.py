from __future__ import annotations

from dataclasses import dataclass

from edward.services.decision_engine import Decision, DecisionResult
from edward.services.expected_value_engine_v08 import ExpectedValueResult
from edward.services.opportunity_engine import OpportunityResult
from edward.services.analysis_service import StrategyResult


@dataclass(frozen=True, slots=True)
class DecisionPolicyV08:
    """Form a v0.8 trade decision from the already computed analytics."""

    buy_threshold: float = 70.0
    add_threshold: float = 75.0
    wait_threshold: float = 45.0
    minimum_confidence: float = 50.0

    @staticmethod
    def _result(
        decision: Decision,
        reason_code: str,
        explanation: str,
        *,
        strategy: StrategyResult | None,
        opportunity: OpportunityResult,
    ) -> DecisionResult:
        return DecisionResult(
            decision=decision,
            status=__import__("edward.services.decision_engine", fromlist=["DecisionStatus"]).DecisionStatus.VALID,
            reason_codes=(reason_code,),
            explanation=explanation,
            strategy_name=strategy.strategy if strategy is not None else None,
            strategy_score=strategy.score if strategy is not None else 0.0,
            opportunity_score=opportunity.score,
        )

    def evaluate_new_position(
        self,
        *,
        strategy: StrategyResult | None,
        expected_value: ExpectedValueResult,
        opportunity: OpportunityResult,
        confidence_score: float,
        entry_ok: bool,
        market_ok: bool,
        risk_ok: bool,
        critical_risk: bool = False,
    ) -> DecisionResult:
        if critical_risk or not risk_ok:
            return self._result(
                Decision.PASS,
                "RISK_FAIL",
                "Открытие позиции запрещено из-за нарушения риск-ограничений.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if strategy is None or not strategy.quality_gate:
            return self._result(
                Decision.PASS,
                "STRATEGY_QUALITY_FAIL",
                "Ни одна стратегия не прошла v0.8 Quality Gate; открытие новой позиции запрещено.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if not expected_value.available or expected_value.observations == 0:
            return self._result(
                Decision.WAIT,
                "EV_UNAVAILABLE",
                "Исторического торгового evidence недостаточно для открытия позиции; требуется дополнительное подтверждение.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if expected_value.expected_value_pct <= 0.0:
            return self._result(
                Decision.PASS,
                "NEGATIVE_EV",
                f"Исторический Expected Value отрицательный ({expected_value.expected_value_pct:+.2f}%).",
                strategy=strategy,
                opportunity=opportunity,
            )

        ci_crosses_zero = (
            expected_value.ev_ci_low_pct is None
            or expected_value.ev_ci_high_pct is None
            or expected_value.ev_ci_low_pct <= 0.0 <= expected_value.ev_ci_high_pct
        )
        if ci_crosses_zero or confidence_score < self.minimum_confidence:
            return self._result(
                Decision.WAIT,
                "EDGE_NOT_RELIABLE",
                "Исторический EV положительный, но надёжность edge недостаточна для открытия новой позиции.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if not market_ok:
            return self._result(
                Decision.WAIT,
                "MARKET_REGIME_UNFAVORABLE",
                "Торговое преимущество подтверждено, но текущий рыночный режим неблагоприятен.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if not entry_ok:
            return self._result(
                Decision.WAIT,
                "ENTRY_NOT_READY",
                "Торговое преимущество и риск приемлемы, но текущая точка входа не подтверждена.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if opportunity.score >= self.buy_threshold:
            return self._result(
                Decision.BUY,
                "BUY_CONDITIONS_MET",
                "Quality Gate пройден, EV положительный и статистически подтверждён, риск, режим, вход и Opportunity Score находятся в допустимых пределах.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if opportunity.score >= self.wait_threshold:
            return self._result(
                Decision.WAIT,
                "OPPORTUNITY_BELOW_BUY_THRESHOLD",
                "Торговое преимущество подтверждено, но итоговая привлекательность ниже порога покупки.",
                strategy=strategy,
                opportunity=opportunity,
            )

        return self._result(
            Decision.PASS,
            "OPPORTUNITY_TOO_LOW",
            "Торговая возможность недостаточно привлекательна по совокупности аналитических показателей.",
            strategy=strategy,
            opportunity=opportunity,
        )

    def evaluate_existing_position(
        self,
        *,
        strategy: StrategyResult | None,
        expected_value: ExpectedValueResult,
        opportunity: OpportunityResult,
        confidence_score: float,
        entry_ok: bool,
        market_ok: bool,
        risk_ok: bool,
        critical_risk: bool = False,
        exit_signal: bool = False,
    ) -> DecisionResult:
        if exit_signal or critical_risk:
            reason = "EXIT_SIGNAL" if exit_signal else "CRITICAL_RISK"
            return self._result(
                Decision.SELL,
                reason,
                "Выполнено критическое условие полного выхода из позиции.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if not risk_ok:
            return self._result(
                Decision.REDUCE,
                "RISK_DETERIORATION",
                "Риск позиции ухудшился; позицию следует сократить.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if not expected_value.available or expected_value.observations == 0:
            return self._result(
                Decision.HOLD,
                "EV_UNAVAILABLE",
                "Недостаточно исторических исходов для обоснованного изменения позиции; текущая рекомендация — HOLD.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if expected_value.expected_value_pct < 0.0:
            ci_confirmed_negative = (
                expected_value.ev_ci_high_pct is not None
                and expected_value.ev_ci_high_pct < 0.0
            )
            if ci_confirmed_negative:
                return self._result(
                    Decision.REDUCE,
                    "NEGATIVE_EV_CONFIRMED",
                    f"Expected Value отрицательный ({expected_value.expected_value_pct:+.2f}%) и его 95% доверительный интервал ниже нуля; позицию следует сократить.",
                    strategy=strategy,
                    opportunity=opportunity,
                )
            return self._result(
                Decision.HOLD,
                "NEGATIVE_EV_UNCERTAIN",
                f"Expected Value отрицательный ({expected_value.expected_value_pct:+.2f}%), но статистически не подтверждён; оснований для немедленного REDUCE недостаточно.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if critical_risk:
            return self._result(
                Decision.SELL,
                "CRITICAL_RISK",
                "Критический риск требует полного выхода из позиции.",
                strategy=strategy,
                opportunity=opportunity,
            )

        ci_crosses_zero = (
            expected_value.ev_ci_low_pct is None
            or expected_value.ev_ci_high_pct is None
            or expected_value.ev_ci_low_pct <= 0.0 <= expected_value.ev_ci_high_pct
        )
        if ci_crosses_zero or confidence_score < self.minimum_confidence:
            return self._result(
                Decision.HOLD,
                "EDGE_NOT_RELIABLE",
                f"EV остаётся положительным ({expected_value.expected_value_pct:+.2f}%), но надёжность edge недостаточна для увеличения или сокращения позиции; текущая рекомендация — HOLD.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if strategy is not None and not strategy.quality_gate:
            return self._result(
                Decision.HOLD,
                "STRATEGY_QUALITY_DEGRADED",
                "EV остаётся положительным, но стратегия не прошла текущий Quality Gate; оснований для автоматического REDUCE недостаточно — HOLD.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if not market_ok:
            return self._result(
                Decision.HOLD,
                "MARKET_REGIME_UNFAVORABLE",
                "Рыночный режим неблагоприятен, но EV и риск не дают достаточного основания для автоматического сокращения; HOLD.",
                strategy=strategy,
                opportunity=opportunity,
            )

        if opportunity.score >= self.add_threshold and entry_ok:
            return self._result(
                Decision.ADD,
                "ADD_CONDITIONS_MET",
                "EV статистически подтверждён, риск приемлем и текущая возможность достаточно привлекательна для увеличения позиции.",
                strategy=strategy,
                opportunity=opportunity,
            )

        return self._result(
            Decision.HOLD,
            "POSITION_VALID",
            "EV положительный, риск приемлем, а данных для изменения позиции недостаточно; текущая рекомендация — HOLD.",
            strategy=strategy,
            opportunity=opportunity,
        )


__all__ = ["DecisionPolicyV08"]
