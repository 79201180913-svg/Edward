from __future__ import annotations

from decimal import Decimal
from typing import Any

from edward.domain.execution import ExecutionDecision, ExecutionRequest


_EXECUTABLE = {"BUY": ExecutionDecision.BUY, "ADD": ExecutionDecision.ADD, "REDUCE": ExecutionDecision.REDUCE, "SELL": ExecutionDecision.SELL}


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def build_execution_request(*, account_id: str, result: Any) -> ExecutionRequest:
    """Convert a validated opportunity result into an immutable execution snapshot."""
    decision_raw = str(getattr(result, "decision", "") or "").upper()
    decision = _EXECUTABLE.get(decision_raw)
    if decision is None:
        raise ValueError(f"decision is not executable: {decision_raw or 'EMPTY'}")
    if not bool(getattr(result, "execution_ready", False)):
        raise ValueError("execution request requires execution_ready=True")

    quantity = int(getattr(result, "recommended_quantity", 0) or 0)
    if quantity <= 0:
        raise ValueError("execution request requires positive recommended_quantity")

    trade_plan = getattr(result, "trade_plan", None)
    entry_price = _decimal(getattr(trade_plan, "entry_price", None)) if trade_plan is not None else None
    if entry_price is None:
        entry_price = _decimal(getattr(result, "price", None))
    if entry_price is None or entry_price <= 0:
        raise ValueError("execution request requires a positive entry price")

    stop_price = _decimal(getattr(trade_plan, "stop_price", None)) if trade_plan is not None else None
    side = "BUY" if decision in {ExecutionDecision.BUY, ExecutionDecision.ADD} else "SELL"
    execution_id = f"{account_id}:{result.instrument_uid}:{decision.value}:{quantity}"

    return ExecutionRequest(
        execution_id=execution_id,
        account_id=str(account_id),
        instrument_uid=str(result.instrument_uid),
        ticker=str(result.ticker),
        decision=decision,
        side=side,
        quantity=Decimal(quantity),
        order_type="LIMIT",
        entry_price=entry_price,
        stop_price=stop_price,
        strategy=getattr(result, "strategy_name", None),
        strategy_score=float(getattr(result, "strategy_score", 0.0) or 0.0),
        opportunity_score=float(getattr(result, "opportunity_score", 0.0) or 0.0),
        risk_score=float(getattr(result, "risk_score", 0.0) or 0.0),
        execution_ready=True,
        recommended_quantity=quantity if False else None,
    )
