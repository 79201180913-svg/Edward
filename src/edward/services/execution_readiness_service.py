from __future__ import annotations

from dataclasses import dataclass


EXECUTION_READINESS_VERSION = "0.6.0"


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
    """Pre-trade gate with separate rules for entry and exit actions."""

    _VALID_DECISIONS = {"BUY", "ADD", "HOLD", "REDUCE", "SELL"}
    _ENTRY_DECISIONS = {"BUY", "ADD"}
    _EXIT_DECISIONS = {"REDUCE", "SELL"}
    _ACTIONABLE_DECISIONS = _ENTRY_DECISIONS | _EXIT_DECISIONS

    @classmethod
    def evaluate(cls, data: ExecutionReadinessInput) -> ExecutionReadinessResult:
        decision = str(data.decision).upper()
        reasons: list[str] = []

        if decision not in cls._VALID_DECISIONS:
            reasons.append("INVALID_DECISION")

        is_entry = decision in cls._ENTRY_DECISIONS
        is_exit = decision in cls._EXIT_DECISIONS
        is_actionable = decision in cls._ACTIONABLE_DECISIONS

        # Forecast and strategy quality gates protect opening/increasing exposure.
        # A failed strategy is instead a valid reason for REDUCE/SELL and must not
        # block the exit itself.
        if is_entry and not data.forecast_quality_pass:
            reasons.append("FORECAST_QUALITY_GATE_FAIL")
        if is_entry and not data.strategy_quality_pass:
            reasons.append("STRATEGY_QUALITY_GATE_FAIL")

        if not data.risk_ok:
            reasons.append("RISK_NOT_OK")
        if is_entry and not data.portfolio_available:
            reasons.append("PORTFOLIO_NOT_AVAILABLE")
        if not data.trading_status_ok:
            reasons.append("TRADING_STATUS_NOT_OK")

        if is_actionable and not data.position_size_ready:
            reasons.append("POSITION_SIZE_NOT_READY")

        # Entry plans require an entry/target/stop. Exit plans only need the
        # executable reduction/close quantity; their forecast target and stop
        # are informational rather than blocking execution gates.
        if is_entry and not data.entry_ready:
            reasons.append("ENTRY_NOT_READY")
        if is_entry and not data.target_ready:
            reasons.append("TARGET_NOT_READY")
        if is_entry and not data.stop_ready:
            reasons.append("STOP_NOT_READY")

        if is_actionable and not data.liquidity_ok:
            reasons.append("LIQUIDITY_NOT_OK")

        # Positive risk/reward is an entry criterion. REDUCE/SELL are risk
        # reduction actions and must not require a positive entry-style RR.
        if is_entry and not data.risk_reward_ok:
            reasons.append("RISK_REWARD_NOT_ACCEPTABLE")

        # HOLD is intentionally informational and never requires sizing,
        # liquidity, entry, target, stop or RR gates.
        if decision == "HOLD":
            reasons.clear()

        return ExecutionReadinessResult(
            execution_ready=not reasons,
            reasons=tuple(reasons),
        )
