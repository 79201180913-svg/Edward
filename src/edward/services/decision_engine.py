from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


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
    portfolio_allows_add: bool = False
    exit_signal: bool = False
    profile: str = "medium_term"


@dataclass(frozen=True, slots=True)
class DecisionResult:
    decision: Decision
    status: DecisionStatus
    reason_codes: tuple[str, ...]
    explanation: str
    decision_engine_version: str = DECISION_ENGINE_VERSION
    strategy_name: str | None = None
    strategy_score: float = 0.0
    opportunity_score: float = 0.0


class DecisionEngine:
    """Beta decision layer above Strategy Analysis and Risk Analysis.

    The engine intentionally does not calculate strategy metrics. It consumes
    their outputs and turns them into an actionable business decision.
    """

    BUY_THRESHOLD = {
        "long_term": 70.0,
        "medium_term": 70.0,
        "speculative": 65.0,
    }
    WAIT_THRESHOLD = {
        "long_term": 45.0,
        "medium_term": 45.0,
        "speculative": 40.0,
    }
    ADD_THRESHOLD = {
        "long_term": 75.0,
        "medium_term": 75.0,
        "speculative": 70.0,
    }

    @classmethod
    def evaluate(cls, request: DecisionRequest) -> DecisionResult:
        try:
            return cls._evaluate(request)
        except Exception as exc:
            return DecisionResult(
                decision=Decision.PASS if request.position.is_open is False else Decision.HOLD,
                status=DecisionStatus.ERROR,
                reason_codes=("DECISION_ENGINE_ERROR",),
                explanation=f"Decision Engine error: {exc}",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=request.opportunity.opportunity_score,
            )

    @classmethod
    def _evaluate(cls, request: DecisionRequest) -> DecisionResult:
        if request.profile not in cls.BUY_THRESHOLD:
            return DecisionResult(
                decision=Decision.PASS if not request.position.is_open else Decision.HOLD,
                status=DecisionStatus.ANALYSIS_UNAVAILABLE,
                reason_codes=("UNSUPPORTED_PROFILE",),
                explanation=f"Unsupported trading profile: {request.profile}",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=request.opportunity.opportunity_score,
            )

        if not request.opportunity.strategy_ok and not request.position.is_open:
            return cls._new_position_failure(request)

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
        threshold = cls.BUY_THRESHOLD[request.profile]
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

        if not request.strategy_quality:
            return cls._new_position_failure(request)

        if not opportunity.market_regime_compatible or not opportunity.entry_ok:
            return DecisionResult(
                decision=Decision.WAIT,
                status=DecisionStatus.VALID,
                reason_codes=("ENTRY_NOT_READY",),
                explanation="Стратегия подходит инструменту, но текущие условия входа недостаточно привлекательны.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=opportunity.opportunity_score,
            )

        if opportunity.opportunity_score >= threshold:
            return DecisionResult(
                decision=Decision.BUY,
                status=DecisionStatus.VALID,
                reason_codes=("BUY_CONDITIONS_MET",),
                explanation="Стратегия прошла Quality Gate, условия входа и риск находятся в допустимых пределах.",
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
        p = request.position
        o = request.opportunity

        if request.exit_signal or o.critical_risk or (not request.strategy_quality and not o.risk_ok):
            reason = "EXIT_SIGNAL" if request.exit_signal else "RISK_OR_STRATEGY_FAIL"
            return DecisionResult(
                decision=Decision.SELL,
                status=DecisionStatus.VALID,
                reason_codes=(reason,),
                explanation="Условия сохранения позиции нарушены; требуется полный выход.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=o.opportunity_score,
            )

        if not o.risk_ok:
            return DecisionResult(
                decision=Decision.REDUCE,
                status=DecisionStatus.VALID,
                reason_codes=("RISK_DETERIORATION",),
                explanation="Риск позиции ухудшился; позицию следует сократить.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=o.opportunity_score,
            )

        if p.target_weight_pct > 0 and p.portfolio_weight_pct > p.target_weight_pct:
            return DecisionResult(
                decision=Decision.REDUCE,
                status=DecisionStatus.VALID,
                reason_codes=("POSITION_ABOVE_TARGET",),
                explanation="Текущий вес позиции превышает целевой размер; позицию следует сократить.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=o.opportunity_score,
            )

        add_threshold = cls.ADD_THRESHOLD[request.profile]
        if (
            request.strategy_quality
            and o.risk_ok
            and o.entry_ok
            and o.opportunity_score >= add_threshold
            and request.portfolio_allows_add
            and (p.target_weight_pct <= 0 or p.portfolio_weight_pct < p.target_weight_pct)
        ):
            return DecisionResult(
                decision=Decision.ADD,
                status=DecisionStatus.VALID,
                reason_codes=("ADD_CONDITIONS_MET",),
                explanation="Сигнал сохраняется, риск приемлем, а текущий размер позиции ниже целевого.",
                strategy_name=request.strategy_name,
                strategy_score=request.strategy_score,
                opportunity_score=o.opportunity_score,
            )

        return DecisionResult(
            decision=Decision.HOLD,
            status=DecisionStatus.VALID,
            reason_codes=("POSITION_VALID",),
            explanation="Текущая позиция сохраняет приемлемое качество и риск; позицию следует удерживать.",
            strategy_name=request.strategy_name,
            strategy_score=request.strategy_score,
            opportunity_score=o.opportunity_score,
        )

    @classmethod
    def rank_opportunities(cls, requests: Iterable[DecisionRequest]) -> list[DecisionResult]:
        results = [cls.evaluate(request) for request in requests]
        priority = {Decision.BUY: 0, Decision.WAIT: 1, Decision.PASS: 2}
        return sorted(
            results,
            key=lambda result: (priority.get(result.decision, 99), -result.opportunity_score),
        )
