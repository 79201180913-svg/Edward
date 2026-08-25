from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


DECISION_ENGINE_VERSION = "0.4.0"


class PositionContext(str, Enum):
    NO_POSITION = "NO_POSITION"
    POSITION_OPEN = "POSITION_OPEN"


class Scenario(str, Enum):
    SINGLE_INSTRUMENT = "SINGLE_INSTRUMENT"
    OPPORTUNITY_SEARCH = "OPPORTUNITY_SEARCH"


class Decision(str, Enum):
    BUY = "BUY"
    WAIT = "WAIT"
    PASS = "PASS"
    HOLD = "HOLD"
    ADD = "ADD"
    REDUCE = "REDUCE"
    SELL = "SELL"


class DecisionStatus(str, Enum):
    VALID = "VALID"
    ANALYSIS_UNAVAILABLE = "ANALYSIS_UNAVAILABLE"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class PositionContextData:
    quantity: float = 0.0
    average_price: float | None = None
    current_price: float | None = None
    pnl: float | None = None
    portfolio_weight_pct: float = 0.0
    target_weight_pct: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.quantity > 0


@dataclass(frozen=True, slots=True)
class OpportunityContext:
    opportunity_score: float = 0.0
    entry_ok: bool = False
    risk_ok: bool = False
    strategy_ok: bool = False
    market_regime_compatible: bool = True
    critical_risk: bool = False


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    scenario: Scenario = Scenario.SINGLE_INSTRUMENT
    position: PositionContextData = field(default_factory=PositionContextData)
    opportunity: OpportunityContext = field(default_factory=OpportunityContext)
    strategy_score: float = 0.0
    strategy_name: str | None = None
    strategy_quality: bool = False
    portfolio_allows_buy: bool = True
    portfolio_allows_add: bool = False
    exit_signal: bool = False
    strategy_quality_degraded: bool = False
    signal_degraded: bool = False
    market_regime_degraded: bool = False
    market_data_available: bool = True
    strategy_analysis_available: bool = True
    risk_analysis_available: bool = True
    portfolio_context_available: bool = True
    instrument_available: bool = True
    profile: str = "medium_term"


@dataclass(frozen=True, slots=True)
class DecisionResult:
    decision: Decision | None
    status: DecisionStatus
    reason_codes: tuple[str, ...]
    explanation: str
    decision_engine_version: str = DECISION_ENGINE_VERSION
    strategy_name: str | None = None
    strategy_score: float = 0.0
    opportunity_score: float = 0.0


class DecisionEngine:
    """Business decision layer above market, strategy, risk and portfolio analysis."""

    BUY_THRESHOLD = {"long_term": 70.0, "medium_term": 70.0, "speculative": 65.0}
    WAIT_THRESHOLD = {"long_term": 45.0, "medium_term": 45.0, "speculative": 40.0}
    ADD_THRESHOLD = {"long_term": 75.0, "medium_term": 75.0, "speculative": 70.0}

    @classmethod
    def evaluate(cls, request: DecisionRequest) -> DecisionResult:
        try:
            return cls._evaluate(request)
        except Exception as exc:
            return cls._technical_result(request, DecisionStatus.ERROR, "DECISION_ENGINE_ERROR", f"Decision Engine error: {exc}")

    @classmethod
    def _technical_result(
        cls,
        request: DecisionRequest,
        status: DecisionStatus,
        reason: str,
        explanation: str,
    ) -> DecisionResult:
        return DecisionResult(
            decision=None,
            status=status,
            reason_codes=(reason,),
            explanation=explanation,
            strategy_name=request.strategy_name,
            strategy_score=request.strategy_score,
            opportunity_score=request.opportunity.opportunity_score,
        )

    @classmethod
    def _evaluate(cls, request: DecisionRequest) -> DecisionResult:
        if request.profile not in cls.BUY_THRESHOLD:
            return cls._technical_result(
                request,
                DecisionStatus.ANALYSIS_UNAVAILABLE,
                "UNSUPPORTED_PROFILE",
                f"Unsupported trading profile: {request.profile}",
            )

        unavailable = []
        if not request.instrument_available:
            unavailable.append("INSTRUMENT_UNAVAILABLE")
        if not request.market_data_available:
            unavailable.append("MARKET_DATA_UNAVAILABLE")
        if not request.strategy_analysis_available:
            unavailable.append("STRATEGY_ANALYSIS_UNAVAILABLE")
        if not request.risk_analysis_available:
            unavailable.append("RISK_ANALYSIS_UNAVAILABLE")
        if request.position.is_open and not request.portfolio_context_available:
            unavailable.append("PORTFOLIO_CONTEXT_UNAVAILABLE")
        if unavailable:
            return DecisionResult(
                decision=None,
                status=DecisionStatus.ANALYSIS_UNAVAILABLE,
                reason_codes=tuple(unavailable),
                explanation="Критически важные данные для формирования торгового решения недоступны.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=request.opportunity.opportunity_score,
            )

        if request.scenario == Scenario.OPPORTUNITY_SEARCH:
            return cls._new_position(request)
        if request.position.is_open:
            return cls._open_position(request)
        return cls._new_position(request)

    @classmethod
    def _new_position_failure(cls, request: DecisionRequest) -> DecisionResult:
        reasons = []
        if not request.strategy_quality:
            reasons.append("STRATEGY_QUALITY_FAIL")
        if not request.opportunity.risk_ok:
            reasons.append("RISK_FAIL")
        if not request.opportunity.market_regime_compatible:
            reasons.append("MARKET_REGIME_UNFAVORABLE")
        if not request.portfolio_allows_buy:
            reasons.append("PORTFOLIO_CONSTRAINT")
        if not reasons:
            reasons.append("NO_ACCEPTABLE_STRATEGY")
        return DecisionResult(
            decision=Decision.PASS,
            status=DecisionStatus.VALID,
            reason_codes=tuple(reasons),
            explanation="Инструмент не имеет достаточного торгового преимущества для открытия позиции.",
            strategy_name=request.strategy_name,
            strategy_score=request.strategy_score,
            opportunity_score=request.opportunity.opportunity_score,
        )

    @classmethod
    def _new_position(cls, request: DecisionRequest) -> DecisionResult:
        opportunity = request.opportunity
        buy_threshold = cls.BUY_THRESHOLD[request.profile]
        wait_threshold = cls.WAIT_THRESHOLD[request.profile]

        if opportunity.critical_risk or not opportunity.risk_ok:
            return DecisionResult(
                decision=Decision.PASS,
                status=DecisionStatus.VALID,
                reason_codes=("RISK_FAIL",),
                explanation="Открытие позиции запрещено из-за нарушения риск-ограничений.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        if not request.strategy_quality or not opportunity.strategy_ok:
            return cls._new_position_failure(request)

        if not request.portfolio_allows_buy:
            return DecisionResult(
                decision=Decision.PASS,
                status=DecisionStatus.VALID,
                reason_codes=("PORTFOLIO_CONSTRAINT",),
                explanation="Открытие позиции запрещено портфельными ограничениями.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        if not opportunity.market_regime_compatible or not opportunity.entry_ok:
            reason = "MARKET_REGIME_UNFAVORABLE" if not opportunity.market_regime_compatible else "ENTRY_NOT_READY"
            return DecisionResult(
                decision=Decision.WAIT,
                status=DecisionStatus.VALID,
                reason_codes=(reason,),
                explanation="Стратегия подходит инструменту, но текущие условия входа недостаточно привлекательны.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        if opportunity.opportunity_score >= buy_threshold:
            return DecisionResult(
                decision=Decision.BUY,
                status=DecisionStatus.VALID,
                reason_codes=("BUY_CONDITIONS_MET",),
                explanation="Стратегия прошла Quality Gate, условия входа, риск и портфельные ограничения находятся в допустимых пределах.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        if opportunity.opportunity_score >= wait_threshold:
            return DecisionResult(
                decision=Decision.WAIT,
                status=DecisionStatus.VALID,
                reason_codes=("OPPORTUNITY_BELOW_BUY_THRESHOLD",),
                explanation="Инструмент потенциально интересен, но текущая привлекательность ниже порога покупки.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        return DecisionResult(
            decision=Decision.PASS,
            status=DecisionStatus.VALID,
            reason_codes=("OPPORTUNITY_TOO_LOW",),
            explanation="Текущая торговая возможность недостаточно привлекательна.",
            strategy_name=request.strategy_name,
            strategy_score=request.strategy_score,
            opportunity_score=opportunity.opportunity_score,
        )

    @classmethod
    def _open_position(cls, request: DecisionRequest) -> DecisionResult:
        position = request.position
        opportunity = request.opportunity

        if request.exit_signal or opportunity.critical_risk:
            reason = "EXIT_SIGNAL" if request.exit_signal else "CRITICAL_RISK"
            return DecisionResult(
                decision=Decision.SELL,
                status=DecisionStatus.VALID,
                reason_codes=(reason,),
                explanation="Выполнено критическое условие полного выхода из позиции.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        if not opportunity.risk_ok:
            return DecisionResult(
                decision=Decision.REDUCE,
                status=DecisionStatus.VALID,
                reason_codes=("RISK_DETERIORATION",),
                explanation="Риск позиции ухудшился; позицию следует сократить.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        if request.strategy_quality_degraded or request.signal_degraded:
            reasons = []
            if request.strategy_quality_degraded:
                reasons.append("STRATEGY_QUALITY_DEGRADED")
            if request.signal_degraded:
                reasons.append("SIGNAL_DEGRADED")
            return DecisionResult(
                decision=Decision.REDUCE,
                status=DecisionStatus.VALID,
                reason_codes=tuple(reasons),
                explanation="Качество стратегии или торгового сигнала ухудшилось; позицию следует сократить.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        if request.market_regime_degraded or not opportunity.market_regime_compatible:
            return DecisionResult(
                decision=Decision.REDUCE,
                status=DecisionStatus.VALID,
                reason_codes=("MARKET_REGIME_UNFAVORABLE",),
                explanation="Текущий рыночный режим стал неблагоприятным для удержания позиции; позицию следует сократить.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        if position.target_weight_pct > 0 and position.portfolio_weight_pct > position.target_weight_pct:
            return DecisionResult(
                decision=Decision.REDUCE,
                status=DecisionStatus.VALID,
                reason_codes=("POSITION_ABOVE_TARGET",),
                explanation="Текущий вес позиции превышает целевой размер; позицию следует сократить.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        add_threshold = cls.ADD_THRESHOLD[request.profile]
        if (
            request.strategy_quality
            and opportunity.strategy_ok
            and opportunity.risk_ok
            and opportunity.market_regime_compatible
            and opportunity.entry_ok
            and opportunity.opportunity_score >= add_threshold
            and request.portfolio_allows_add
            and (position.target_weight_pct <= 0 or position.portfolio_weight_pct < position.target_weight_pct)
        ):
            return DecisionResult(
                decision=Decision.ADD,
                status=DecisionStatus.VALID,
                reason_codes=("ADD_CONDITIONS_MET",),
                explanation="Сигнал сохраняется, риск приемлем, а текущий размер позиции ниже целевого.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        return DecisionResult(
            decision=Decision.HOLD,
            status=DecisionStatus.VALID,
            reason_codes=("POSITION_VALID",),
            explanation="Стратегия и риск остаются приемлемыми; условия полного выхода и сокращения отсутствуют.",
            strategy_name=request.strategy_name,
            strategy_score=request.strategy_score,
            opportunity_score=opportunity.opportunity_score,
        )

    @classmethod
    def rank_opportunities(cls, requests: Iterable[DecisionRequest]) -> list[DecisionResult]:
        results = [cls.evaluate(request) for request in requests]
        priority = {Decision.BUY: 0, Decision.WAIT: 1, Decision.PASS: 2}
        return sorted(results, key=lambda result: (priority.get(result.decision, 99), -result.opportunity_score))

    @classmethod
    def main_opportunities(cls, requests: Iterable[DecisionRequest]) -> list[DecisionResult]:
        return [result for result in cls.rank_opportunities(requests) if result.decision in {Decision.BUY, Decision.WAIT}]
