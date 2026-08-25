from __future__ import annotations

from dataclasses import dataclass


EXECUTION_READINESS_VERSION = "0.5.0"


@dataclass(frozen=True, slots=True)
class ExecutionReadinessInput:
    decision: str
    forecast_quality_pass: bool
    risk_ok: bool
    portfolio_available: bool
    trading_status_ok: bool
    position_size_ready: bool
    entry_ready: bool
    target_ready: bool
    stop_ready: bool
    liquidity_ok: bool
    strategy_quality_pass: bool = True
    risk_reward_ok: bool = True


@dataclass(frozen=True, slots=True)
class ExecutionReadinessResult:
    execution_ready: bool
    reasons: tuple[str, ...]
    version: str = EXECUTION_READINESS_VERSION


class ExecutionReadinessService:
    """Pre-trade gate for future Execution Engine integration."""

    _VALID_DECISIONS = {"BUY", "ADD", "HOLD", "REDUCE", "SELL"}
    _ACTIONABLE_DECISIONS = {"BUY", "ADD", "REDUCE", "SELL"}

    @classmethod
    def evaluate(cls, data: ExecutionReadinessInput) -> ExecutionReadinessResult:
        decision = str(data.decision).upper()
        reasons: list[str] = []

        if decision not in cls._VALID_DECISIONS:
            reasons.append("INVALID_DECISION")
        if decision in {"BUY", "ADD"} and not data.forecast_quality_pass:
            reasons.append("FORECAST_QUALITY_GATE_FAIL")
        if decision in cls._ACTIONABLE_DECISIONS and not data.strategy_quality_pass:
            reasons.append("STRATEGY_QUALITY_GATE_FAIL")
        if not data.risk_ok:
            reasons.append("RISK_NOT_OK")
        if decision in {"BUY", "ADD"} and not data.portfolio_available:
            reasons.append("PORTFOLIO_NOT_AVAILABLE")
        if not data.trading_status_ok:
            reasons.append("TRADING_STATUS_NOT_OK")
        if decision in cls._ACTIONABLE_DECISIONS and not data.position_size_ready:
            reasons.append("POSITION_SIZE_NOT_READY")
        if decision in {"BUY", "ADD"} and not data.entry_ready:
            reasons.append("ENTRY_NOT_READY")
        if decision in cls._ACTIONABLE_DECISIONS and not data.target_ready:
            reasons.append("TARGET_NOT_READY")
        if decision in cls._ACTIONABLE_DECISIONS and not data.stop_ready:
            reasons.append("STOP_NOT_READY")
        if decision in cls._ACTIONABLE_DECISIONS and not data.liquidity_ok:
            reasons.append("LIQUIDITY_NOT_OK")
        if decision in cls._ACTIONABLE_DECISIONS and not data.risk_reward_ok:
            reasons.append("RISK_REWARD_NOT_ACCEPTABLE")

        return ExecutionReadinessResult(
            execution_ready=not reasons,
            reasons=tuple(reasons),
        )
