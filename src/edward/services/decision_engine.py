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
class InstrumentContextData:
    instrument_uid: str | None = None
    ticker: str | None = None
    buy_available: bool = True
    sell_available: bool = True
    trading_status: str | None = None
    available: bool = True


@dataclass(frozen=True, slots=True)
class MarketContextData:
    current_price: float | None = None
    close_price: float | None = None
    market_regime: str | None = None
    trend: str | None = None
    momentum: str | None = None
    volatility: float | None = None
    entry_level: float | None = None
    stop_level: float | None = None
    target_level: float | None = None
    regime_compatible: bool = True
    entry_ok: bool = False
    available: bool = True


@dataclass(frozen=True, slots=True)
class StrategyContextData:
    strategy_id: str | None = None
    strategy_name: str | None = None
    strategy_score: float = 0.0
    walk_forward_score: float | None = None
    stability_score: float | None = None
    confidence: str | None = None
    quality_gate: bool = False
    entry_signal: bool = False
    exit_signal: bool = False
    quality_degraded: bool = False
    signal_degraded: bool = False
    available: bool = True


@dataclass(frozen=True, slots=True)
class RiskContextData:
    risk_gate: bool = True
    critical_risk: bool = False
    risk_score: float | None = None
    max_drawdown_pct: float | None = None
    risk_reward: float | None = None
    available: bool = True


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
class PortfolioContextData:
    portfolio_value: float | None = None
    available_cash: float | None = None
    blocked_cash: float | None = None
    current_weight_pct: float = 0.0
    target_weight_pct: float = 0.0
    max_position_weight_pct: float | None = None
    allows_buy: bool = True
    allows_add: bool = True
    available: bool = True


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
    instrument: InstrumentContextData = field(default_factory=InstrumentContextData)
    market: MarketContextData = field(default_factory=MarketContextData)
    strategy: StrategyContextData = field(default_factory=StrategyContextData)
    risk: RiskContextData = field(default_factory=RiskContextData)
    position: PositionContextData = field(default_factory=PositionContextData)
    portfolio: PortfolioContextData = field(default_factory=PortfolioContextData)
    opportunity: OpportunityContext = field(default_factory=OpportunityContext)

    # Backward-compatible beta fields kept for existing callers/tests.
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

    def effective_strategy_name(self) -> str | None:
        return self.strategy.strategy_name if self.strategy.strategy_name is not None else self.strategy_name

    def effective_strategy_score(self) -> float:
        return self.strategy.strategy_score if self.strategy.strategy_name is not None or self.strategy.strategy_score != 0.0 else self.strategy_score

    def effective_strategy_quality(self) -> bool:
        return self.strategy.quality_gate if self.strategy.strategy_name is not None or self.strategy.quality_gate else self.strategy_quality

    def effective_exit_signal(self) -> bool:
        return self.strategy.exit_signal if self.strategy.strategy_name is not None or self.strategy.exit_signal else self.exit_signal

    def effective_risk_ok(self) -> bool:
        return self.risk.risk_gate if not self.risk.available else (self.risk.risk_gate and self.opportunity.risk_ok)

    def effective_critical_risk(self) -> bool:
        return self.risk.critical_risk or self.opportunity.critical_risk

    def effective_market_compatible(self) -> bool:
        return self.market.regime_compatible and self.opportunity.market_regime_compatible

    def effective_entry_ok(self) -> bool:
        return self.market.entry_ok if self.market.market_regime is not None or self.market.entry_ok else self.opportunity.entry_ok

    def effective_portfolio_allows_buy(self) -> bool:
        return self.portfolio.allows_buy and self.portfolio_allows_buy

    def effective_portfolio_allows_add(self) -> bool:
        return self.portfolio.allows_add and self.portfolio_allows_add


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
    def _technical_result(cls, request: DecisionRequest, status: DecisionStatus, reason: str, explanation: str) -> DecisionResult:
        return DecisionResult(
            decision=None,
            status=status,
            reason_codes=(reason,),
            explanation=explanation,
            strategy_name=request.effective_strategy_name(),
            strategy_score=request.effective_strategy_score(),
            opportunity_score=request.opportunity.opportunity_score,
        )

    @classmethod
    def _evaluate(cls, request: DecisionRequest) -> DecisionResult:
        if request.profile not in cls.BUY_THRESHOLD:
            return cls._technical_result(request, DecisionStatus.ANALYSIS_UNAVAILABLE, "UNSUPPORTED_PROFILE", f"Unsupported trading profile: {request.profile}")

        unavailable = []
        if not request.instrument_available or not request.instrument.available:
            unavailable.append("INSTRUMENT_UNAVAILABLE")
        if not request.market_data_available or not request.market.available:
            unavailable.append("MARKET_DATA_UNAVAILABLE")
        if not request.strategy_analysis_available or not request.strategy.available:
            unavailable.append("STRATEGY_ANALYSIS_UNAVAILABLE")
        if not request.risk_analysis_available or not request.risk.available:
            unavailable.append("RISK_ANALYSIS_UNAVAILABLE")
        if request.position.is_open and (not request.portfolio_context_available or not request.portfolio.available):
            unavailable.append("PORTFOLIO_CONTEXT_UNAVAILABLE")
        if unavailable:
            return DecisionResult(
                decision=None,
                status=DecisionStatus.ANALYSIS_UNAVAILABLE,
                reason_codes=tuple(unavailable),
                explanation="Критически важные данные для формирования торгового решения недоступны.",
                strategy_name=request.effective_strategy_name(),
                strategy_score=request.effective_strategy_score(),
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
        if not request.effective_strategy_quality() or not request.opportunity.strategy_ok:
            reasons.append("STRATEGY_QUALITY_FAIL")
        if not request.opportunity.risk_ok or not request.risk.risk_gate:
            reasons.append("RISK_FAIL")
        if not request.effective_market_compatible():
            reasons.append("MARKET_REGIME_UNFAVORABLE")
        if not request.effective_portfolio_allows_buy():
            reasons.append("PORTFOLIO_CONSTRAINT")
        if not reasons:
            reasons.append("NO_ACCEPTABLE_STRATEGY")
        return DecisionResult(
            decision=Decision.PASS,
            status=DecisionStatus.VALID,
            reason_codes=tuple(reasons),
            explanation="Инструмент не имеет достаточного торгового преимущества для открытия позиции.",
            strategy_name=request.effective_strategy_name(),
            strategy_score=request.effective_strategy_score(),
            opportunity_score=request.opportunity.opportunity_score,
        )

    @classmethod
    def _new_position(cls, request: DecisionRequest) -> DecisionResult:
        opportunity = request.opportunity
        buy_threshold = cls.BUY_THRESHOLD[request.profile]
        wait_threshold = cls.WAIT_THRESHOLD[request.profile]

        if request.effective_critical_risk() or not request.opportunity.risk_ok or not request.risk.risk_gate:
            return DecisionResult(Decision.PASS, DecisionStatus.VALID, ("RISK_FAIL",), "Открытие позиции запрещено из-за нарушения риск-ограничений.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        if not request.effective_strategy_quality() or not opportunity.strategy_ok:
            return cls._new_position_failure(request)

        if not request.effective_portfolio_allows_buy() or not request.instrument.buy_available:
            reason = "PORTFOLIO_CONSTRAINT" if not request.effective_portfolio_allows_buy() else "INSTRUMENT_BUY_UNAVAILABLE"
            return DecisionResult(Decision.PASS, DecisionStatus.VALID, (reason,), "Открытие позиции запрещено текущими торговыми или портфельными ограничениями.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        if not request.effective_market_compatible() or not request.effective_entry_ok():
            reason = "MARKET_REGIME_UNFAVORABLE" if not request.effective_market_compatible() else "ENTRY_NOT_READY"
            return DecisionResult(Decision.WAIT, DecisionStatus.VALID, (reason,), "Стратегия подходит инструменту, но текущие условия входа недостаточно привлекательны.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        if opportunity.opportunity_score >= buy_threshold:
            return DecisionResult(Decision.BUY, DecisionStatus.VALID, ("BUY_CONDITIONS_MET",), "Стратегия прошла Quality Gate, условия входа, риск и портфельные ограничения находятся в допустимых пределах.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        if opportunity.opportunity_score >= wait_threshold:
            return DecisionResult(Decision.WAIT, DecisionStatus.VALID, ("OPPORTUNITY_BELOW_BUY_THRESHOLD",), "Инструмент потенциально интересен, но текущая привлекательность ниже порога покупки.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        return DecisionResult(Decision.PASS, DecisionStatus.VALID, ("OPPORTUNITY_TOO_LOW",), "Текущая торговая возможность недостаточно привлекательна.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

    @classmethod
    def _open_position(cls, request: DecisionRequest) -> DecisionResult:
        position = request.position
        opportunity = request.opportunity

        if request.effective_exit_signal() or request.effective_critical_risk():
            reason = "EXIT_SIGNAL" if request.effective_exit_signal() else "CRITICAL_RISK"
            return DecisionResult(Decision.SELL, DecisionStatus.VALID, (reason,), "Выполнено критическое условие полного выхода из позиции.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        if not opportunity.risk_ok or not request.risk.risk_gate:
            return DecisionResult(Decision.REDUCE, DecisionStatus.VALID, ("RISK_DETERIORATION",), "Риск позиции ухудшился; позицию следует сократить.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        if not request.effective_strategy_quality() or not opportunity.strategy_ok:
            return DecisionResult(Decision.REDUCE, DecisionStatus.VALID, ("STRATEGY_QUALITY_FAIL",), "Качество стратегии стало неприемлемым; позицию следует сократить.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        if request.strategy_quality_degraded or request.signal_degraded or request.strategy.quality_degraded or request.strategy.signal_degraded:
            reasons = []
            if request.strategy_quality_degraded or request.strategy.quality_degraded:
                reasons.append("STRATEGY_QUALITY_DEGRADED")
            if request.signal_degraded or request.strategy.signal_degraded:
                reasons.append("SIGNAL_DEGRADED")
            return DecisionResult(Decision.REDUCE, DecisionStatus.VALID, tuple(reasons), "Качество стратегии или торгового сигнала ухудшилось; позицию следует сократить.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        if request.market_regime_degraded or not request.effective_market_compatible():
            return DecisionResult(Decision.REDUCE, DecisionStatus.VALID, ("MARKET_REGIME_UNFAVORABLE",), "Текущий рыночный режим стал неблагоприятным для удержания позиции; позицию следует сократить.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        target_weight = position.target_weight_pct or request.portfolio.target_weight_pct
        current_weight = position.portfolio_weight_pct or request.portfolio.current_weight_pct
        if target_weight > 0 and current_weight > target_weight:
            return DecisionResult(Decision.REDUCE, DecisionStatus.VALID, ("POSITION_ABOVE_TARGET",), "Текущий вес позиции превышает целевой размер; позицию следует сократить.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        add_threshold = cls.ADD_THRESHOLD[request.profile]
        allows_add = request.effective_portfolio_allows_add()
        below_target = target_weight <= 0 or current_weight < target_weight
        if opportunity.opportunity_score >= add_threshold and allows_add and opportunity.entry_ok and below_target:
            return DecisionResult(Decision.ADD, DecisionStatus.VALID, ("ADD_CONDITIONS_MET",), "Сигнал сохраняется, риск приемлем, а текущий размер позиции ниже целевого.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

        return DecisionResult(Decision.HOLD, DecisionStatus.VALID, ("POSITION_VALID",), "Стратегия и риск остаются приемлемыми; условия полного выхода и сокращения отсутствуют.", strategy_name=request.effective_strategy_name(), strategy_score=request.effective_strategy_score(), opportunity_score=opportunity.opportunity_score)

    @classmethod
    def rank_opportunities(cls, requests: Iterable[DecisionRequest]) -> list[DecisionResult]:
        results = [cls.evaluate(request) for request in requests]
        priority = {Decision.BUY: 0, Decision.WAIT: 1, Decision.PASS: 2}
        return sorted(results, key=lambda result: (priority.get(result.decision, 99), -result.opportunity_score))

    @classmethod
    def main_opportunities(cls, requests: Iterable[DecisionRequest]) -> list[DecisionResult]:
        return [result for result in cls.rank_opportunities(requests) if result.decision in {Decision.BUY, Decision.WAIT}]
